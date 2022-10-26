import aws_cdk as core
import aws_cdk.assertions as assertions

from ssm_cleaner.ssm_cleaner_stack import SsmCleanerStack

# example tests. To run these tests, uncomment this file along with the example
# resource in ssm_cleaner/ssm_cleaner_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = SsmCleanerStack(app, "ssm-cleaner")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
