"""A CIDR opening on task HTTP must prevent accepting a forwarded-HTTPS boundary."""

from typing import Any

import pytest

from scripts import verify_staging_network


@pytest.mark.parametrize("cidr", [False, True])
def test_only_alb_group_can_reach_task_http(cidr: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    permission = {
        "IpProtocol": "tcp",
        "FromPort": 8000,
        "ToPort": 8000,
        "UserIdGroupPairs": [{"GroupId": "sg-alb", "UserId": "028364485203"}],
    }
    if cidr:
        permission["IpRanges"] = [{"CidrIp": "0.0.0.0/0"}]

    def read(*args: str) -> dict[str, Any]:
        if args[1] == "describe-express-gateway-service":
            return {
                "service": {
                    "status": {"statusCode": "ACTIVE"},
                    "activeConfigurations": [
                        {
                            "serviceRevisionArn": "revision",
                            "networkConfiguration": {"securityGroups": ["sg-task"]},
                        }
                    ],
                }
            }
        if args[1] == "describe-service-revisions":
            return {
                "serviceRevisions": [
                    {"resolvedConfiguration": {"loadBalancers": [{"targetGroupArn": "target"}]}}
                ]
            }
        if args[1] == "describe-target-groups":
            return {"TargetGroups": [{"LoadBalancerArns": ["balancer"]}]}
        if args[1] == "describe-load-balancers":
            return {"LoadBalancers": [{"VpcId": "vpc-staging", "SecurityGroups": ["sg-alb"]}]}
        return {
            "SecurityGroups": [
                {
                    "VpcId": "vpc-staging",
                    "IpPermissions": [] if args[-1] == "sg-app" else [permission],
                }
            ]
        }

    monkeypatch.setattr(verify_staging_network, "aws", read)
    if cidr:
        with pytest.raises(RuntimeError, match="CIDR"):
            verify_staging_network.verify_ingress("cluster", "service", "sg-app")
    else:
        assert (
            verify_staging_network.verify_ingress("cluster", "service", "sg-app")[
                "task_ingress_from_alb_only"
            ]
            is True
        )


def test_missing_revision_resolution_cannot_accept_proxy_trust(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        verify_staging_network,
        "aws",
        lambda *args: {"service": {"status": {"statusCode": "ACTIVE"}, "activeConfigurations": []}},
    )
    with pytest.raises(RuntimeError, match="No active Express revision"):
        verify_staging_network.verify_ingress("cluster", "service", "sg-app")
