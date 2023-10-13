import os
from typing import List

import torch
from sentence_transformers import util, SentenceTransformer

from app.course.schemas import ResearchNote

EMBEDDING_DIM = 384

os.environ["TOKENIZERS_PARALLELISM"] = "false"


def create_embeddings(passages, model) -> torch.Tensor:
    return model.encode(passages, convert_to_tensor=True)


def run_query(
    query_text: str | List[str], embeddings, model, result_count=1, score_thresh=0.6
):
    query_embedding = model.encode(query_text, convert_to_tensor=True)

    cos_scores = util.cos_sim(query_embedding, embeddings)
    top_results = torch.topk(cos_scores, k=result_count, dim=-1)

    # Indices of the passages most similar to the queries (outline items)
    flat_indices = torch.flatten(top_results.indices[top_results.values > score_thresh])
    selected_row = torch.sum(top_results.values > score_thresh, dim=-1) > 0
    selected_indices = set(flat_indices.tolist())

    # Create a mapping, so we know which passages are used by which outline items
    if isinstance(query_text, list):
        outline_items_selected = torch.arange(len(query_text))[selected_row].tolist()
        item_mapping = {o: i.item() for o, i in zip(outline_items_selected, flat_indices)}
    else:
        item_mapping = None
    return top_results, selected_indices, item_mapping


def dedup_list(topics, score_thresh=0.9):
    tc = TopicEmbedding()
    clean_topics = topics[:1]
    tc.add_topics(clean_topics)

    for topic in topics[1:]:
        res = tc.query(topic, score_thresh=score_thresh)
        if len(res) == 0:
            clean_topics.append(topic)
        try:
            tc.add_topics([topic])
        except KeyError:
            pass
    return clean_topics


class TopicEmbedding:
    def __init__(self):
        self.embeddings = None
        self.topics = []
        self.model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

    def add_topics(self, topics):
        for topic in topics:
            self.topics.append(topic)
            embeddings = create_embeddings(topic, self.model)

            embeddings = embeddings.reshape(1, -1)
            if embeddings.shape[1] != EMBEDDING_DIM:
                print(f"Error embedding topic: {topic}")
                continue

            if self.embeddings is None:
                self.embeddings = embeddings
            else:
                self.embeddings = torch.cat((self.embeddings, embeddings), dim=0)

    def query(self, query_text, result_count=1, score_thresh=0.9) -> List[str]:
        try:
            scores, selected_indices, item_mapping = run_query(
                query_text, self.embeddings, self.model, result_count, score_thresh=score_thresh
            )
        except KeyError as e:
            print(f"Error querying topic embedding: {e}")
            return []

        results = []
        for index in selected_indices:
            results.append(self.topics[index])

        return results


class EmbeddingContext:
    def __init__(self, model):
        self.embeddings = None
        self.content = []
        self.lengths = []
        self.text_data = []
        self.model = model
        self.kinds = []

    def add_resources(self, resources):
        for resource in resources:
            self.content += resource.content
            self.lengths.append(len(self.content))
            self.kinds.append(resource.kind)

            embeddings = create_embeddings(resource.content, self.model)

            embeddings = embeddings.reshape(len(resource.content), -1)
            if embeddings.shape[1] != EMBEDDING_DIM:
                print(f"Error embedding resource")
                continue

            if self.embeddings is None:
                self.embeddings = embeddings
            else:
                self.embeddings = torch.cat((self.embeddings, embeddings), dim=0)

            self.text_data.append(resource)

    def query(self, query_text, result_count=1, score_thresh=0.6) -> List[ResearchNote]:
        scores, selected_indices, item_mapping = run_query(
            query_text, self.embeddings, self.model, result_count, score_thresh=score_thresh
        )

        results = []
        for index in selected_indices:
            for i, length in enumerate(self.lengths):
                if index < length:
                    text_data = self.text_data[i]
                    result = ResearchNote(
                        content=self.content[index],
                        outline_items=[k for k in item_mapping.keys() if item_mapping[k] == index],
                        kind=self.kinds[i]
                    )
                    results.append(result)
                    break

        return results
