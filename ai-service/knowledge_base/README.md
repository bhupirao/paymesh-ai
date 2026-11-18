# Curated PayMesh knowledge

Eight allowlisted Markdown documents contain stable Document-ID, Title, Scenarios
and Sources headers, followed by verified behavior and separately labeled general
guidance. Source references point into the read-only Java backend; they are not
fetched or treated as network URLs. Only the eight filenames in retrieval.py load.
No uploads, arbitrary paths, external URLs, embeddings or vector database are used.

Chunks are at most 800 characters. IDs combine document ID, chunk ordinal and
content hash, stable across identical loads. Editing content changes affected chunk
IDs; changing chunk boundaries can change subsequent IDs. Retrieval uses standard
library TF-IDF cosine similarity, not semantic vector search. Scores measure lexical
relevance, never payment certainty. The corpus is small and curated, not exhaustive.

## Phase6.9.1 chat corpus extension

Investigation continues to load the same original8 filenames; its corpus/order is unchanged.
Chat separately loads those8 plus routing,links,checkout,eligibility,statistics (13 IDs).
New material documents implemented V12/V13 rules, not proof of live activation. No actual
customer records, identifiers, checkout tokens or credentials belong in the corpus.
Canonical topic retrieval uses the existing bounded TF-IDF implementation. Chat validates
actual chunks/metadata, returns their stable IDs and local KB source paths, but forwards
no raw retrieved prose to the model. Model wording choices are restricted to approved
server answers; retrieval score is relevance, never financial certainty.
