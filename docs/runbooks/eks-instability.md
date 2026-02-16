---
title: EKS Instability
service: Kubernetes / EKS
owner: Platform Engineering
category: Infrastructure
tags: [eks, kubernetes, scaling, stability, pods, oom, evictions]
last_reviewed: 2026-01-03
---

# EKS Instability: pod evictions, OOM kills, node pressure

## Symptoms

- Frequent pod evictions or CrashLoopBackOff states
- OOMKilled events in pod logs
- Nodes in `NotReady` state
- Cluster autoscaler failing to provision new nodes
- Deployment rollouts stuck in pending state

## Checks

1. **Node pressure and resource usage**
    ```bash
    kubectl top nodes
    kubectl describe nodes | grep -A5 "Conditions"
    ```

2. **Pod eviction events**
    ```bash
    kubectl get events --sort-by='.lastTimestamp' -n <namespace> | grep -i evict
    ```

3. **Identify noisy deployments or runaway jobs**
    ```bash
    kubectl top pods --sort-by=memory -n <namespace> | head -20
    ```

4. **Cluster autoscaler events**
    ```bash
    kubectl logs -n kube-system deploy/cluster-autoscaler | tail -50
    ```
    Look for `ScaleUp` failures or `NotReady` node errors.

5. **Recent deployments or config changes**
    ```bash
    kubectl rollout history deployment/<name> -n <namespace>
    ```

## Mitigations

- **Scale out nodes** manually if autoscaler is stuck
    ```bash
    aws eks update-nodegroup-config --cluster-name <cluster> --nodegroup-name <group> --scaling-config minSize=X,maxSize=Y,desiredSize=Z
    ```
- **Reduce concurrency** for heavy consumer pods (lower replica count or resource requests)
- **Pause non-critical cronjobs** to free resources
- **Restart affected pods** to clear OOM state
    - Use the **Restart EKS Pods** action
- **Scale up the service** if the root cause is under-provisioning
    - Use the **Scale Service** action

## Escalation

!!! warning "Escalation threshold"
    Escalate if cluster health cannot stabilise within **30 minutes** of mitigation actions, or if node provisioning failures affect production workloads.
