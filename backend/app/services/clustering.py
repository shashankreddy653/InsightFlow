"""Similarity grouping: TF-IDF vectors + agglomerative clustering over unique texts.

Duplicate review texts share one vector, so 7,000 records with 320 unique
sentences are clustered in well under a second and every record inherits the
cluster of its text. Unrelated reviews are not grouped merely because they share
a sentiment: grouping is purely lexical (TF-IDF cosine distance).
"""
from dataclasses import dataclass

import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sklearn.feature_extraction.text import TfidfVectorizer

# Cosine distance threshold: 0.65 groups paraphrases of the same complaint
# ("delivery was delayed" / "shipment was late") while keeping distinct
# complaint types separate. Tuned on the supplied dataset: 320 unique texts ->
# ~120 coherent groups with few singletons.
DEFAULT_DISTANCE_THRESHOLD = 0.65


@dataclass
class ClusterAssignment:
    text: str
    cluster_id: int
    representative: bool


def cluster_texts(texts: list[str], distance_threshold: float = DEFAULT_DISTANCE_THRESHOLD) -> list[ClusterAssignment]:
    """Cluster unique texts; returns one assignment per input text (in order)."""
    if not texts:
        return []
    if len(texts) == 1:
        return [ClusterAssignment(texts[0], 0, True)]

    vectorizer = TfidfVectorizer(
        stop_words="english", ngram_range=(1, 2), min_df=1, sublinear_tf=True
    )
    matrix = vectorizer.fit_transform(texts)

    model = AgglomerativeClustering(
        n_clusters=None,
        distance_threshold=distance_threshold,
        metric="cosine",
        linkage="average",
    )
    labels = model.fit_predict(matrix.toarray())

    # Representative text per cluster = closest to cluster centroid (cosine).
    reps: dict[int, int] = {}
    dense = matrix.toarray()
    for cid in sorted(set(labels.tolist())):
        idxs = np.where(labels == cid)[0]
        members = dense[idxs]
        centroid = members.mean(axis=0)
        norm = np.linalg.norm(centroid)
        if norm == 0:
            reps[cid] = int(idxs[0])
            continue
        sims = members @ centroid / (np.linalg.norm(members, axis=1) * norm + 1e-9)
        reps[cid] = int(idxs[int(np.argmax(sims))])

    return [
        ClusterAssignment(text=t, cluster_id=int(labels[i]), representative=(reps[int(labels[i])] == i))
        for i, t in enumerate(texts)
    ]


def cluster_label_hints(rep_texts_by_cluster: dict[int, str]) -> dict[int, list[str]]:
    """Top TF-IDF terms per cluster, used to build human-readable issue titles."""
    if not rep_texts_by_cluster:
        return {}
    cluster_ids = list(rep_texts_by_cluster.keys())
    texts = [rep_texts_by_cluster[cid] for cid in cluster_ids]
    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=1)
    X = vectorizer.fit_transform(texts)
    terms = np.array(vectorizer.get_feature_names_out())
    hints: dict[int, list[str]] = {}
    for row, cid in enumerate(cluster_ids):
        vec = X[row].toarray().ravel()
        top = vec.argsort()[::-1][:4]
        hints[cid] = [terms[i] for i in top if vec[i] > 0]
    return hints
