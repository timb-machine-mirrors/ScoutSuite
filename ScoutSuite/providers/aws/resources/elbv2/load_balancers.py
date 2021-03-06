from ScoutSuite.providers.aws.resources.resources import AWSCompositeResources
from ScoutSuite.providers.utils import get_non_provider_id
from .listeners import Listeners


class LoadBalancers(AWSCompositeResources):
    _children = [
        (Listeners, 'listeners')
    ]

    async def fetch_all(self, **kwargs):
        raw_load_balancers = await self.facade.elbv2.get_load_balancers(self.scope['region'], self.scope['vpc'])
        for raw_load_balancer in raw_load_balancers:
            id, load_balancer = self._parse_load_balancer(raw_load_balancer)
            self[id] = load_balancer

        await self._fetch_children_of_all_resources(
            resources=self,
            scopes={load_balancer_id: {'region': self.scope['region'], 'load_balancer_arn': load_balancer['arn']}
                    for (load_balancer_id, load_balancer) in self.items()}
        )

    def _parse_load_balancer(self, load_balancer):
        load_balancer['arn'] = load_balancer.pop('LoadBalancerArn')
        load_balancer['name'] = load_balancer.pop('LoadBalancerName')
        load_balancer['security_groups'] = []

        if 'SecurityGroups' in load_balancer:
            for sg in load_balancer['SecurityGroups']:
                load_balancer['security_groups'].append({'GroupId': sg})
            load_balancer.pop('SecurityGroups')

        return get_non_provider_id(load_balancer['name']), load_balancer
