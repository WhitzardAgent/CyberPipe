---
license: cc-by-4.0
task_categories:
  - text-generation
track_downloads: true
configs:
- config_name: Nemotron-Pretraining-Formal-Logic
  data_files:
    - split: train
      path: Nemotron-Pretraining-Formal-Logic/*.parquet
- config_name: Nemotron-Pretraining-Economics
  data_files:
    - split: train
      path: Nemotron-Pretraining-Economics/*.parquet
- config_name: Nemotron-Pretraining-Multiple-Choice
  data_files:
    - split: train
      path: Nemotron-Pretraining-Multiple-Choice/*.parquet
- config_name: Nemotron-Pretraining-Unconditional-Algorithmic
  data_files:
    - split: train
      path: Nemotron-Pretraining-Unconditional-Algorithmic/*.parquet
- config_name: Nemotron-Pretraining-Code-Concepts
  data_files:
    - split: train
      path: Nemotron-Pretraining-Code-Concepts/*.parquet
---
# Nemotron-Pretraining-Specialized-v1.1

## Dataset Description:

The [Nemotron-Pretraining-Specialized-v1.1](https://huggingface.co/datasets/nvidia/Nemotron-Pretraining-Specialized-v1.1) dataset is part of the [Nemotron Pretraining Data](https://huggingface.co/collections/nvidia/nemotron-pre-training-datasets) collection of pretraining datasets. Designed for the [NVIDIA Nemotron 3](https://huggingface.co/collections/nvidia/nvidia-nemotron-v3) family of LLMs, this dataset contains a collection of synthetic datasets aimed to improve LLM capabilities in code concepts and algorithms, formal logic, economics, and multiple choice questions. The code concepts dataset is an instance of a general methodology we developed for large-scale, concept-driven synthetic data generation, as described in [this blog](https://huggingface.co/blog/nvidia/synthetic-code-concepts).

Note: These are new datasets, not replacements. They may be used in conjunction with the previously released datasets of [Nemotron-Pretraining-Specialized-v1](https://huggingface.co/datasets/nvidia/Nemotron-Pretraining-Specialized-v1).

This dataset is ready for commercial use.

## Dataset Details:

For more details, please see the [NVIDIA  Nemotron  3  Super  tech  report](https://research.nvidia.com/labs/nemotron/files/NVIDIA-Nemotron-3-Super-Technical-Report.pdf).

This dataset has the following subsets:
- **Synthetic Code Concepts ([blog](https://huggingface.co/blog/nvidia/synthetic-code-concepts))**: Python problems and solutions generated from combinations of high-level programming concepts organized in a taxonomical form (e.g., algorithms.technique.linear-search, analytics.techniques.modular-arithmetic, data-structures.arrays.matrix, functionality.data-processing.conversion).
- **Synthetic Unconditional Algorithmic**: Python samples in various formats generated from minimalistic prompts like "Write a function."
- **Synthetic Economics**: Multiple choice questions and answers about economics, with and without chain-of-thought.
- **Synthetic Formal Logic**: Multiple choice questions and answers about formal logic, with and without chain-of-thought. Contains examples designed for several patterns, e.g., natural language to formal logic, formal logic to natural language, solving problems using truth tables, etc.
- **Synthetic Multiple Choice**: Multiple choice questions and answers about a variety of topics found in the MMLU auxiliary_train dataset.

The table below shows the number of tokens and the model used to generate these subsets:

|  Subset  |  Tokens (M)  |  Models  | License |
|  ---  |  ---  |  ---  | --- |
|  **Nemotron-Pretraining-Code-Concepts**  |  7294.5  |  gpt-oss-20b, gpt-oss-120b  | cc-by-4.0 |
|  **Nemotron-Pretraining-Unconditional-Algorithmic**  |  195.4  |  gpt-oss-120b, Qwen3-235B-A22B  | cc-by-4.0 |
|  **Nemotron-Pretraining-Formal-Logic**  |  128.0 |  Qwen3-235B-A22B-Thinking-2507  | cc-by-4.0 |
|  **Nemotron-Pretraining-Economics**  |  73.4  |  Qwen3-235B-A22B-Thinking-2507  | cc-by-4.0 |
|  **Nemotron-Pretraining-Multiple-Choice**  |  1609.2  |  DeepSeek-v3, Qwen3-235B-A22B  | cc-by-4.0 |

The columns are as follows:

- **text**: The **primary data field,** containing the content to be used for pretraining.
- **license**: The license(s) governing the sample (e.g., ‘cc-by-4.0’).
- **metadata**: A dictionary detailing the following:
    - **category**: Data type (e.g., 'Nemotron-Pretraining-Code-Concepts', 'Nemotron-Pretraining-Economics', ...).
    - **models_used**: Models used to generate the data (e.g., 'gpt-oss-120b').
    - For Nemotron-Pretraining-Code-Concepts, there are the following additional entries:
        - **function_name:** Name of the generated function (e.g., "detect_no_dup_range_gcd_mod").
        - **tags:** Comma-separated list of tags used to generate the prompt (e.g., "algorithms.arrays.ranges,algorithms.duplicate-detection,analytics.techniques.modular-arithmetic,algorithms.math.gcd").
        - **problem_prompt:** The prompt used to generate the sample.
        - **generated_solution:** The full response to the prompt, including thinking trace.
- **uuid**: The unique identifier for this dataset entry.

## Dataset Owner(s):

NVIDIA Corporation

## Dataset Creation Date:

01/23/2026

## License/Terms of Use:

The **Nemotron-Pretraining-Specialized-v1.1** dataset is governed by the [Creative Commons Attribution 4.0 International License](https://creativecommons.org/licenses/by/4.0/) (CC BY 4.0)

This dataset contains synthetic data created using the following models:

Qwen3-235B-A22B-Thinking-2507, Qwen3-235B-A22B, DeepSeek-v3, gpt-oss-20b, gpt-oss-120b.

If the **Nemotron-Pretraining-Multiple-Choice** subset of this dataset is used to create, train, fine-tune, or otherwise improve an AI model, which is distributed or made available, such AI model may be subject to redistribution and use requirements in the [DeepSeek License Agreement](https://huggingface.co/deepseek-ai/DeepSeek-V3/blob/main/LICENSE-MODEL).

## Intended Usage:

The Nemotron-Pre-Training-Specialized-v1.1 Dataset is intended to be used by the community to continue to improve open models.

## Dataset Characterization

**Data Collection Method**

- Synthetic: Synthetic generation using large language models (Qwen3-235B-A22B-Thinking-2507, Qwen3-235B-A22B, DeepSeek-v3, gpt-oss-20b, gpt-oss-120b).

**Labeling Method**

- Not Applicable

## Dataset Format

Modality: Text

Format: Parquet

## Dataset Quantification

Record Count: 19.8M samples

Measurement of Total Data Storage: 34.9 GB

## Reference(s):

If  you  use  our  dataset  in  your  research,  please  cite  our  [NVIDIA  Nemotron  3  Super  tech  report](https://research.nvidia.com/labs/nemotron/files/NVIDIA-Nemotron-3-Super-Technical-Report.pdf).

For more details on the Code Concepts dataset, please see [Code Concepts: A Large-Scale Synthetic Dataset Generated from Programming Concept Seeds](https://huggingface.co/blog/nvidia/synthetic-code-concepts).

## Ethical Considerations:

NVIDIA believes Trustworthy AI is a shared responsibility and we have established policies and practices to enable development for a wide array of AI applications.  When downloaded or used in accordance with our terms of service, developers should work with their internal developer teams to ensure this dataset meets requirements for the relevant industry and use case and addresses unforeseen product misuse.

Please report quality, risk, security vulnerabilities or NVIDIA AI Concerns [here](https://www.nvidia.com/en-us/support/submit-security-vulnerability/).
