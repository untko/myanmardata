# Usage

List the available collectors:

```sh
myanmardata sources
```

Collect one or more sources into a data directory:

```sh
myanmardata collect superrich_th --out data
```

Use `--dry-run` to fetch and parse without writing anything.

Import a Viber channel's history from Viber Desktop's `viber.db` (see the README for where it lives):

```sh
myanmardata viber chats viber.db
myanmardata import baht_kyat --viber-db viber.db --out data
```

From Python:

```python
from myanmardata.collectors import registry
from myanmardata.store import SnapshotStore

collection = registry()["superrich_th"].collect()
SnapshotStore("data").write(
    collection.source, collection.records, collection.collected_at, collection.raw, collection.raw_ext
)
```
