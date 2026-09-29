---
dataset_info:
  features:
  - name: language
    dtype: string
  - name: original_code
    dtype: string
  - name: code_with_imports
    dtype: string
  - name: path_in_repo
    dtype: string
  - name: seed_uuid
    dtype: string
  - name: token_count
    dtype: int64
  - name: original_code_token_count
    dtype: int64
  - name: lsp_hop_hitrate
    dtype: float64
  - name: lsp_hop_count
    dtype: float64
  - name: in_repo_percent
    dtype: float64
  - name: num_py_lib_imports
    dtype: int64
  - name: num_third_party_imports
    dtype: int64
  - name: num_first_party_imports
    dtype: int64
  splits:
  - name: train
    num_bytes: 6119968992
    num_examples: 10000
  download_size: 2149146734
  dataset_size: 6119968992
configs:
- config_name: default
  data_files:
  - split: train
    path: data/train-*
---
