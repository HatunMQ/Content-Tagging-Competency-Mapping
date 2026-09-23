# Content Tagging Model - Sample Dataset

## Objective
Build and evaluate a self-deployed content tagging model that can analyze learning content and return useful structured tags.

For each content item, the model should identify:

1. Key topics and concepts covered in the content
2. Difficulty level

The main goal is to compare candidate models/approaches and select a content-tagging model that performs well and can be deployed efficiently.

## Required output per content item
Return one structured record per file with at least:

- file_name
- model_name
- content_type
- predicted_tags
- difficulty_level
- confidence
- notes

### Difficulty labels
Use only:
- Beginner
- Intermediate
- Advanced

### Tagging guidance
Tags should represent the specific concepts taught in the content rather than only broad domain labels.

For example, prefer:
`DataFrame filtering`, `groupby aggregation`, `missing-value handling`

instead of only:
`Python` or `Data Analysis`

## Evaluation
Run the same content through each candidate model/approach and store the results in `model_output_template.csv`.

The models should be compared against a separately maintained human-reviewed annotation key. In addition to tagging quality, the final model recommendation should consider deployment factors such as latency, resource requirements, and ease of serving.

Do not treat filenames as ground truth. The model should analyze the actual content.
