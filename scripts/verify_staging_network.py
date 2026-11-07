"""Verify the concrete ALB-to-task trust boundary before accepting proxy headers."""

from typing import Any

from scripts.aws_cli import aws


def verify_ingress(cluster: str, service: str, app_group: str) -> dict[str, Any]:
    description = aws("ecs", "describe-services", "--cluster", cluster, "--services", service)[
        "services"
    ][0]
    groups = description["networkConfiguration"]["awsvpcConfiguration"]["securityGroups"]
    expected_vpc = aws("ec2", "describe-security-groups", "--group-ids", app_group)[
        "SecurityGroups"
    ][0]["VpcId"]
    targets = [item["targetGroupArn"] for item in description["loadBalancers"]]
    target_groups = aws("elbv2", "describe-target-groups", "--target-group-arns", *targets)[
        "TargetGroups"
    ]
    balancers = sorted({arn for target in target_groups for arn in target["LoadBalancerArns"]})
    load_balancers = aws("elbv2", "describe-load-balancers", "--load-balancer-arns", *balancers)[
        "LoadBalancers"
    ]
    if not load_balancers or any(lb["VpcId"] != expected_vpc for lb in load_balancers):
        raise RuntimeError("ALB is outside the dedicated staging VPC")
    allowed = {group for lb in load_balancers for group in lb["SecurityGroups"]}
    actual = aws("ec2", "describe-security-groups", "--group-ids", *groups)["SecurityGroups"]
    found = False
    for group in actual:
        if group["VpcId"] != expected_vpc:
            raise RuntimeError("Task security group VPC mismatch")
        for permission in group.get("IpPermissions", []):
            protocol = permission["IpProtocol"]
            covers = protocol == "-1" or (
                protocol in {"tcp", "6"} and permission["FromPort"] <= 8000 <= permission["ToPort"]
            )
            if not covers:
                continue
            if (
                permission.get("IpRanges")
                or permission.get("Ipv6Ranges")
                or permission.get("PrefixListIds")
            ):
                raise RuntimeError("Task HTTP port has CIDR/prefix ingress outside ALB identity")
            for pair in permission.get("UserIdGroupPairs", []):
                if pair["GroupId"] not in allowed or pair.get("UserId") != "028364485203":
                    raise RuntimeError("Task HTTP port accepts a non-ALB security group")
                found = True
    if not found:
        raise RuntimeError("No authenticated ALB security-group ingress found for task port")
    return {"task_ingress_from_alb_only": True, "dedicated_vpc": True}
