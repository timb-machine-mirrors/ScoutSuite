import boto3

from collections import Counter
from botocore.session import Session
from ScoutSuite.providers.utils import run_concurrently
from ScoutSuite.providers.aws.facade.basefacade import AWSBaseFacade
from ScoutSuite.providers.aws.facade.awslambda import LambdaFacade
from ScoutSuite.providers.aws.facade.cloudformation import CloudFormation
from ScoutSuite.providers.aws.facade.cloudtrail import CloudTrailFacade
from ScoutSuite.providers.aws.facade.cloudwatch import CloudWatch
from ScoutSuite.providers.aws.facade.directconnect import DirectConnectFacade
from ScoutSuite.providers.aws.facade.ec2 import EC2Facade
from ScoutSuite.providers.aws.facade.efs import EFSFacade
from ScoutSuite.providers.aws.facade.elasticache import ElastiCacheFacade
from ScoutSuite.providers.aws.facade.emr import EMRFacade
from ScoutSuite.providers.aws.facade.route53 import Route53Facade
from ScoutSuite.providers.aws.facade.sqs import SQSFacade
from ScoutSuite.providers.aws.facade.elbv2 import ELBv2Facade
from ScoutSuite.providers.aws.facade.iam import IAMFacade
from ScoutSuite.providers.aws.facade.rds import RDSFacade
from ScoutSuite.providers.aws.facade.redshift import RedshiftFacade
from ScoutSuite.providers.aws.facade.ses import SESFacade
from ScoutSuite.providers.aws.facade.sns import SNSFacade
from ScoutSuite.providers.aws.facade.elb import ELBFacade

try:
    from ScoutSuite.providers.aws.facade.dynamodb_private import DynamoDBFacade
    from ScoutSuite.providers.aws.facade.config_private import ConfigFacade
    from ScoutSuite.providers.aws.facade.kms_private import KMSFacade
except ImportError:
    pass

  
class AWSFacade(AWSBaseFacade):
    def __init__(self, credentials: dict = None):
        self._set_session(credentials)

    async def build_region_list(self, service: str, chosen_regions=None, partition_name='aws'):
        service = 'ec2containerservice' if service == 'ecs' else service
        available_services = await run_concurrently(lambda: Session().get_available_services())

        if service not in available_services:
            raise Exception('Service ' + service + ' is not available.')

        regions = await run_concurrently(lambda: Session().get_available_regions(service, partition_name))

        if chosen_regions:
            return list((Counter(regions) & Counter(chosen_regions)).elements())
        else:
            return regions

    def _set_session(self, credentials: dict):
        # TODO: This conditional check is ok for now, but eventually, the credentials should always be provided.
        if not credentials:
            self.session = None
            return

        session_params = {'aws_access_key_id': credentials.get('access_key'),
                          'aws_secret_access_key': credentials.get('secret_key'),
                          'aws_session_token': credentials.get('token')}

        self.session = boto3.session.Session(**session_params)

        # TODO: This should only be done in the constructor. I put this here for now, because this method is currently
        # called from outside, but it should not happen.
        self._instantiate_facades()

    def _instantiate_facades(self):
        self.ec2 = EC2Facade(self.session)
        self.awslambda = LambdaFacade(self.session)
        self.cloudformation = CloudFormation(self.session)
        self.cloudtrail = CloudTrailFacade(self.session)
        self.cloudwatch = CloudWatch(self.session)
        self.directconnect = DirectConnectFacade(self.session)
        self.efs = EFSFacade(self.session)
        self.elasticache = ElastiCacheFacade(self.session)
        self.emr = EMRFacade(self.session)
        self.route53 = Route53Facade(self.session)
        self.elb = ELBFacade(self.session)
        self.elbv2 = ELBv2Facade(self.session)
        self.iam = IAMFacade(self.session)
        self.rds = RDSFacade(self.session)
        self.redshift = RedshiftFacade(self.session)
        self.ses = SESFacade(self.session)
        self.sns = SNSFacade(self.session)
        self.sqs = SQSFacade(self.session)

        try:
            self.dynamodb = DynamoDBFacade(self.session)
            self.config = ConfigFacade(self.session)
            self.kms = KMSFacade(self.session)
        except NameError:
            pass