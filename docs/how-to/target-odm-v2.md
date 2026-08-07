# Generate mappers for ODM v2 instead of v3

Every shipped config file in `odm_map_maker/configs/` targets ODM v3. To target
v2, override three options on the command line.

```console
python odm_map_maker/make_mappers_cli.py \
    --config odm_map_maker/configs/nwss_to_odm.yaml \
    --target-schema odm_map_maker/data/odm_v2/linkml/odm_v2.yaml \
    --output-dir ../gen/nwss-reporting-to-v2 \
    --selectors odm=2
```

All three matter:

- `--target-schema` — the v2 LinkML schema instead of v3.
- `--output-dir` — a separate directory, so the v3 output is not overwritten.
  Every run clears CSV, TSV, and YAML files from the directories it writes to.
- `--selectors odm=2` — drops workbook rows tagged `odm>=3.0` and keeps rows
  tagged `odm<3.0`. **Forgetting this produces a mapper that silently omits the
  v2-specific rows**, with no error.

The same three overrides work for the other configs:

```console
# ODM v1 → ODM v2
python odm_map_maker/make_mappers_cli.py \
    --config odm_map_maker/configs/odm_v1_to_odm.yaml \
    --target-schema odm_map_maker/data/odm_v2/linkml/odm_v2.yaml \
    --output-dir ../gen/odm-v1-to-v2 \
    --selectors odm=2

# PHA4GE → ODM v2
python odm_map_maker/make_mappers_cli.py \
    --config odm_map_maker/configs/pha4ge_to_odm.yaml \
    --target-schema odm_map_maker/data/odm_v2/linkml/odm_v2.yaml \
    --output-dir ../gen/pha4ge-to-v2 \
    --selectors odm=2
```

When you check the result, pass the **v2** schema to the checking tools as well
— see [Check generated mappers](check-generated-mappers.md). Running the checker
with the v3 schema against v2 mappers produces a wall of spurious errors.

## Related

- [Selectors](../reference/mapping-config-files.md#selectors) — the full syntax,
  including exclusion (`!tag`) and version comparisons.
- [CLI Configuration Files](../reference/cli-config-files.md) — how config file
  values and command-line arguments interact.
