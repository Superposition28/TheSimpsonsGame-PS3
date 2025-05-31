from .generic_file_indexer import index_generic_file
from .dds_file_indexer import index_dds_file
from .str_archive_indexer import index_str_archive
from .txd_file_indexer import index_txd_file
# Import other indexers here as they are created

# Optionally, a factory function or a dispatch dictionary can be defined here
# to select the correct indexer based on file extension or type.
# For now, the orchestrator will likely call them directly.