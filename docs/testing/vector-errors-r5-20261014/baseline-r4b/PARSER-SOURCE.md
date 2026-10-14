Isolated audit candidate port of serde_json 1.0.149 default numeric de.rs path.
Source: https://github.com/serde-rs/json/tree/v1.0.149
License: MIT OR Apache-2.0; both upstream license files retained here.
parser_port.py is a Python stdlib-only runtime. Rust helper and Chroma are test oracles only.
Query uses Python json.dumps tokens; record replay uses the same bounded compatibility
approximation. Full binary64 formatter equivalence to Zmij is not proven.
Historical r3 numeric_matrix-r3-historical.py preserves the former LO-1 rejection contract;
new r4 supports negative out-of-I64 query tokens, covered by original 84 oracle cases.
