current_phase: 00-foundation
current_prompt: 01-project-skeleton
status: pending

phases:
  00-foundation:
    depends_on: none
    prompts: 01-05

  01-data-model:
    depends_on: 00-foundation
    prompts: 06-15

  02-import:
    depends_on: 01-data-model
    prompts: 16-19

  03-data-quality:
    depends_on: 02-import
    prompts: 20-26

  04-temporal:
    depends_on: 03-data-quality
    prompts: 27-30

  05-baseline:
    depends_on: 04-temporal
    prompts: 31-37

  06-impact:
    depends_on: 01-data-model
    prompts: 38-40

  07-analysis:
    depends_on:
      - 05-baseline
      - 06-impact
    prompts: 41-47

  08-anomaly:
    depends_on: 07-analysis
    prompts: 48-52

  09-trend:
    depends_on: 05-baseline
    prompts: 53-55

  10-knowledge:
    depends_on: 01-data-model
    prompts: 56-61

  11-report:
    depends_on:
      - 08-anomaly
      - 10-knowledge
    prompts: 62-68

  12-frontend:
    depends_on: 11-report
    prompts: 69-75

  13-security:
    depends_on: 12-frontend
    prompts: 76-82

  14-quality:
    depends_on: 13-security
    prompts: 83-88

  15-post-mvp:
    depends_on: 14-quality
    prompts: 89-101
