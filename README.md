# Textbook Quality

This project generates very long, textbook quality pretraining data.  [Here's](https://huggingface.co/datasets/vikp/textbook_quality_programming) a 70M token example.  It can run generations in parallel, against OpenAI, or your own API.  It can generate the topics from scratch, or use a set of seeds you provide.

The generator uses retrieval to improve quality.  By default, it will use [Serply](https://serply.io) to do the retrieval, but you can also use [SerpAPI](https://serpapi.com), or disable retrieval.

The core is extensible, so you can add your own adaptors to connect to new APIs and retrieval backends.

# Installing

## Prerequisites

- Python 3.9+ (ideally 3.11)
- You will need postgres installed. You can install it with `brew install postgres` on a Mac.

## Setup

- `psql postgres -c "create database textbook;"`
- `git clone https://github.com/VikParuchuri/textbook_quality.git`
- `cd textbook_quality`
- `poetry install`
- `invoke migrate-dev`

## Configuration

First, create a `local.env` file in the root directory of the repo to store your secret keys.  Alternatively, you can set any key below as an env var.

You can see all the available configuration values in `app/settings.py`.

### With OpenAI and retrieval (highest quality)

- Add your OpenAI key, like `OPENAI_KEY=sk-xxxxxx`
- Add your serply key (`SERPLY_KEY="..."`) or serpapi key (`SERPAPI_KEY="..."`).
- Add `SEARCH_BACKEND=serply` or `SEARCH_BACKEND=serpapi` to use the appropriate backend.

By default, this will use `gpt-3.5`.  You can use `gpt-4` by setting the env vars `LLM_TYPE`, `LLM_INSTRUCT_TYPE` to `gpt-4`.  You may be able to get away with setting `LLM_EXTENDED_TYPE` to `gpt-4` as well, but you may need longer than 8k context.

### With vllm or other openai-compatible API and retrieval

- Set `OPENAI_KEY` to the value of your API key, or a dummy value.
- Set `OPENAI_BASE_URL` to the url of your API (like https://vllm-api.com/v1)
- Set the `LLM_TYPE`, `LLM_INSTRUCT_TYPE`, and `LLM_EXTENDED_TYPE` settings to your model name (like `llama`)
- Set the model name and max tokens in the `LLM_TYPES` setting.
- Follow the instructions above for the retrieval setup.

The generator ideally needs a context length of up to `16k`, but you can get away with `12k` if you need to.

### Without retrieval

- Set `SEARCH_BACKEND=none`

# Usage

There are three main scripts in the repo.  You can run each script on the output of the previous one.  All outputs will appear by default in `app/data`, which is the specified `DATA_DIR` in settings.

## Generate topics from scratch

You enter a subject, a file you want to save the topics to, and the number of iterations.  The topics will be deduplicated.

Usage example:

`python topic_generator.py "computer science with python" python_cs_titles.json --iterations 50`

## Augment topics from seeds

Take a file with existing seeds (in a flat json list), and augment them.  You can pass in the output file from the topic generator as the seed file, or use your own seeds.  Domain is an optional flag to constrain the topics within a domain.

This will also deduplicate the topics semantically.

Usage example:

`python topic_augmentor.py python_titles.json python_topics.json --domain python`

## Generate textbooks

This will take a file with a flat json list of topics, and generate one textbook per topic.  The workers flag controls the number of parallel generations.  Lower it if you hit rate limits.

Usage example:

`python book_generator.py topics.json books.jsonl --workers 5`

You can also override settings with environment variables (instead of using `local.env`).  This example will use a vllm api instead of openai:

`LLM_TYPE=llama LLM_INSTRUCT_TYPE=llama LLM_EXTENDED_TYPE=llama OPENAI_KEY="llama" OPENAI_BASE_URL="https://vllm-api.com/v1" python book_generator.py topics.json books.jsonl --workers 10`

Note that courses are cached by default, so regenerating a course with the same name twice will not hit the API again.  The cache is specific to each model and each topic.

# Extending

You can extend this to add in new LLM adaptors, retrieval methods, or tasks.  PRs are very welcome.

- LLM adapters are in `app/llm/adaptors`
- Retrieval methods are in `app/services/adaptors`.  You may also need to adjust settings in `services/generators/pdf.py`
- Tasks are in `app/llm/generators`

# Debugging

By default, a lot of exceptions will be hidden to avoid console noise.  Use `DEBUG=true` to display them, like this:

`DEBUG=true python book_generator.py python_topics.json books.jsonl --max 5 --workers 5`