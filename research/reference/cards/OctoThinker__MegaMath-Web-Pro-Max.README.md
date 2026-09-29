---
license: odc-by
extra_gated_prompt: >-
  By using this data, you agree to comply with the license. Access to this dataset is granted
  automatically once you accept the license terms and complete all the required
  fields below.
extra_gated_fields:
  Your Full Name: text
  Organization or Entity you are affiliated with: text
  Country or state you are located in: text
  Your email: text
  What is your intended use(s) for this dataset: text
  You AGREE to use this dataset for non-commercial use ONLY: checkbox
  You AGREE to comply with the original usage licenses of all sources contributing to this dataset and the license of this dataset: checkbox
  You AGREE to cite our paper if you use this dataset: checkbox
  You ENSURE that the information you have provided is true and accurate: checkbox
---

# [OctoThinker: Mid-training Incentivizes Reinforcement Learning Scaling](https://arxiv.org/abs/2506.20512)

![](octothinker_banner.png)


## The Curation of MegaMath-Web-Pro-Max


**Step 1**: Uniformly and randomly sample millions of documents from the MegaMath-Web corpus, stratified by publication year;

**Step 2**: Annotate them using Llama-3.1-70B-instruct with a scoring prompt from FineMath and prepare the seed data;

**Step 3**: Training a fasttext carefully with proper preprocessing;

**Step 4**: Filtering documents with a threshold (i.e., 0.4);

**Step 5**: Refine at scale using Llama-3.1-70B-instruct with a refinement prompt;


<!-- ![](mm_web_pro_max_data_pipeline.png) -->


<div style="display: flex; justify-content: center; gap: 20px;">
<img src="mm_web_pro_max_data_pipeline.png" alt="Data Pipeline" style="width:70%;">
</div>



## Demonstration of Data Quality (from pre/mid-training side)


Following MegaMath-Web’s yearly dump comparison setup (pick top 5B tokens from each year, then continual pre-training tinyllama and report the avg benchmark perf), we evaluate the quality of our recalled corpus under different thresholds, as shown in the Figure below. （Note that here, no data is refined by LLM and all are raw documents filtered from MegaMath)


<div style="display: flex; justify-content: center; gap: 20px;">
<img src="web_data_quality_comparison_yearly.png" alt="data quality" style="width:60%;">
</div>




## Demonstration of Data Quality (from RL side)


Mid-training on math web data improves performance over the base model, with MegaMath-Web-Pro and MegaMath-Web-Pro-Max showing slightly better gains than Finemath-4plus. After RL training, we find that mid-training on math web corpora improves RL

<div style="display: flex; justify-content: center; gap: 20px;">
<img src="data_quality_rl_side.png" alt="data quality"  style="width:80%;">
</div>



## Citation

Check out our [paper](https://arxiv.org/abs/2506.20512) for more details. If you use our dataset or find our work useful, please cite

```
@article{wang2025octothinker,
  title={OctoThinker: Mid-training Incentivizes Reinforcement Learning Scaling},
  author={Wang, Zengzhi and Zhou, Fan and Li, Xuefeng and Liu, Pengfei},
  year={2025},
  journal={arXiv preprint arXiv:2506.20512},
  note={Preprint}
}
```