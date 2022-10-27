"""Stage parameters which will be passed in as environment variables to the lambda"""
parameters = {
    "prod": {
        "PIPELINE_ACCOUNT": "056952386373",
        "ROLE": "PCMCloudAdmin",
        "S3_ACCOUNT": "056952386373",
        "S3_BUCKET": "ami-bakery-data-056952386373-us-east-1",
        "STAGE": "PROD",
    },
    "dev": {
        "PIPELINE_ACCOUNT": "119377359737",
        "ROLE": "PCMCloudAdmin",
        "S3_ACCOUNT": "119377359737",
        "S3_BUCKET": "ami-bakery-data-119377359737-us-east-1",
        "STAGE": "DEV",
    },
}
