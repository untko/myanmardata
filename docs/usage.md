# Usage

List the available collectors:

```sh
myanmardata sources
```

Collect one or more sources into a data directory:

```sh
myanmardata collect superrich_th superrich_1965 --out data
```

Use `--dry-run` to fetch and parse without writing anything.

From Python:

```python
from myanmardata.collectors import registry
from myanmardata.store import SnapshotStore

collection = registry()["superrich_th"].collect()
SnapshotStore("data").write(
    collection.source, collection.records, collection.collected_at, collection.raw, collection.raw_ext
)
```
