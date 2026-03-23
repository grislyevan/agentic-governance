"""Cross-tree correlation hints for analyst explanation and future rules.

Does not change detection outcome; attaches soft correlation between trees
(e.g. tree A read credentials, tree B connected to API).
"""

from .correlation_hints import (
    CorrelationHint,
    CorrelationHintsEngine,
    enrichment_for_tree,
    get_destination_clusters_for_tree,
    get_working_dir_for_tree,
    hints_for_tree,
)

__all__ = [
    "CorrelationHint",
    "CorrelationHintsEngine",
    "enrichment_for_tree",
    "get_destination_clusters_for_tree",
    "get_working_dir_for_tree",
    "hints_for_tree",
]
