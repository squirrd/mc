# Feature Research

**Domain:** Container orchestration CLI for per-case workspace isolation
**Researched:** 2026-01-26
**Confidence:** HIGH

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Create container | Core function - start a new isolated workspace | MEDIUM | Similar to `docker-compose up`, `kind create cluster`, `minikube start`. MC needs: create + start + attach terminal in one command |
| List all containers | Visibility into what's running | LOW | Like `docker-compose ps --all`, `kind get clusters`, `minikube profile`. Must show: case number, status, uptime, resource usage |
| Stop container | Graceful shutdown without destroying data | LOW | Standard in all tools (`docker-compose stop`, `minikube stop`). Preserves workspace/config for resume |
| Start existing container | Resume stopped container | LOW | Pair with stop - users expect start/stop cycles. Like `docker-compose start` |
| Delete container | Clean up when case closed | LOW | Remove container + cleanup resources. Like `docker-compose down`, `kind delete cluster`. Should warn before destructive action |
| Execute command in container | Debug/inspect running environment | MEDIUM | Essential debugging tool (`docker-compose exec`, `kubectl exec`). MC needs: `mc case exec 12345 -- oc get nodes` |
| View container logs | Troubleshoot what happened | MEDIUM | Like `docker-compose logs`, `minikube logs`. Show both MC orchestration logs and container stdout/stderr |
| Check container status | Quick health check for specific case | LOW | Like `docker-compose ps`, `minikube status`. Show: running/stopped/error, uptime, resource limits |
| Restart container | Recover from hung state | LOW | Combine stop + start. Common in all orchestration tools. Useful for config reloads |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not required, but valuable.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Auto-open terminal window | Seamless workflow - one command to workspace | HIGH | **Key differentiator.** `mc case 12345` → new iTerm2/Terminal window attached to container. Automates what users do manually with docker-compose |
| Salesforce metadata auto-resolution | No manual case lookup - tool fetches case details | MEDIUM | Fetch case owner, severity, account from SF API. Auto-populate workspace metadata. Eliminates context switching |
| Persistent container per case | Stateful workspaces survive restarts | LOW | Unlike throw-away dev containers, MC containers persist across sessions. Resume exactly where you left off |
| Resource limits per container | Prevent runaway case from consuming host | MEDIUM | Set memory/CPU limits. Like Kubernetes resource requests. Protects multi-case workflow (5-10 concurrent) |
| Container health monitoring | Proactive detection of stuck containers | MEDIUM | Monitor container metrics, warn if unresponsive. Like Kubernetes liveness probes. Prevent "zombie" containers |
| Bulk operations | Manage multiple cases at once | MEDIUM | `mc case stop --all`, `mc case list --running`. Power user feature for end-of-day cleanup |
| Case attachment to running container | Join existing session without interrupting | LOW | Multiple terminal windows to same case. Like `docker attach` or `screen -x`. Useful for monitoring while working |
| Workspace mount status | Verify case files are accessible | LOW | Show mount points, check /workspace directory. Prevents "where's my data?" confusion |
| Container image versioning | Pin/upgrade MC container image | MEDIUM | `mc case create --image mc:v2.1.0`. Allow testing new images, rollback if broken. Like kind --image flag |
| Shell customization injection | Apply user's dotfiles to container | MEDIUM | Mount ~/.mc/dotfiles into container. Preserve aliases, PS1, vim config. Improves container UX |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| SSH into containers | "I need to inspect the environment" | Installing SSH servers in containers is anti-pattern (security risk, bloat, defeats containerization). SSH won't run if container stops | Use `mc case exec` for command execution, `mc case attach` for interactive shell. Same capability, no SSH daemon |
| GUI/web dashboard | "Visual interface would be nice" | Scope creep. MC is CLI-first tool. Web UI adds complexity, security surface, deployment requirements | Keep CLI focused. If UI needed later, make separate project. Power users prefer CLI speed |
| Plugin system | "Let users extend functionality" | Security nightmare. Version compatibility hell. CLI tools should have focused scope | Build features users actually need into core tool. Defer edge cases |
| Real-time notifications | "Alert me when case container stops" | Not needed for CLI workflow. Adds polling/daemon complexity. Container orchestrators handle this differently | Users check `mc case list` or `mc case status`. Simple, reliable, no background processes |
| Container networking between cases | "Share data between case containers" | Breaks isolation model. Cases should be independent. Adds networking complexity | If data sharing needed, use host filesystem or shared volume mounts. Keep containers isolated |
| Treating containers like VMs | "Run multiple services per container" | Docker anti-pattern. Containers should run single process. Multiple processes complicate lifecycle, logging, debugging | One container = one purpose (case workspace). Use docker-compose if truly need multi-container orchestration |
| Using 'latest' tag for images | "Always use newest version" | Breaks reproducibility. Image updates can introduce breaking changes without warning | Pin specific image versions in config. Allow override with --image flag. Explicit > implicit |
| Running containers as root | "Easier to install packages" | Security risk. If container escapes, has root on host. Bad practice even in dev environments | Use non-root user in Dockerfile. Install necessary packages in image build, not at runtime |

## Feature Dependencies

```
[Create Container]
    ├──requires──> [Container Image] (built/pulled first)
    └──requires──> [Case Workspace Directory] (mount point)

[Auto-open Terminal]
    └──requires──> [Create Container] (terminal attaches to running container)

[Salesforce Integration]
    ├──enhances──> [Create Container] (auto-populate metadata)
    └──enhances──> [List Containers] (show case owner, severity in list view)

[Execute Command]
    └──requires──> [Running Container] (can't exec in stopped container)

[View Logs]
    ├──works-with──> [Stopped Container] (historical logs)
    └──works-with──> [Running Container] (live tail)

[Resource Limits]
    └──requires──> [Create Container] (set at creation time)

[Health Monitoring]
    └──requires──> [Running Container] (monitor active containers)

[Bulk Operations]
    ├──wraps──> [Stop Container] (stop multiple)
    ├──wraps──> [Start Container] (start multiple)
    └──wraps──> [Delete Container] (delete multiple)

[Container Image Versioning]
    └──conflicts──> ['latest' tag usage] (pinning vs always-newest)
```

### Dependency Notes

- **Create requires workspace directory:** Cannot start container without mount point for /workspace. MC must verify case workspace exists (or create it) before container starts
- **Terminal attachment requires running container:** Terminal automation (iTerm2/Terminal.app scripting) only works after container is running. Two-step: create/start, then attach
- **Salesforce enhances but not blocks:** If SF API fails, container creation should still succeed. Metadata fetch is enhancement, not hard dependency
- **Exec requires running container:** Cannot `docker exec` into stopped container. Must check status first, auto-start if stopped, or error clearly
- **Resource limits set at creation:** Docker/containerd resource constraints apply at container start. Cannot change limits on running container (must recreate)
- **Health monitoring vs status check:** Status is point-in-time (`docker inspect`), health monitoring is continuous (periodic checks). Monitoring builds on status
- **Bulk operations wrap singles:** Implement atomic operations first (stop, start, delete), then bulk commands iterate. Avoid duplicating logic

## MVP Definition

### Launch With (v2.0)

Minimum viable product — what's needed to validate the per-case containerization concept.

- [x] **Create container** — Core value proposition. `mc case 12345` creates/starts container for case
- [x] **List all containers** — Essential visibility. `mc case list` shows all case containers with status
- [x] **Stop container** — Required lifecycle management. `mc case stop 12345` graceful shutdown
- [x] **Delete container** — Cleanup when done. `mc case delete 12345` removes container
- [x] **Execute command** — Debugging capability. `mc case exec 12345 -- <command>`
- [x] **Auto-open terminal** — Key differentiator. Makes workflow seamless vs manual docker-compose
- [x] **Container image with tools** — Pre-built image with mc, oc, ocm, backplane on RHEL 10 base
- [x] **Workspace mounting** — Mount case workspace + shared config into container
- [x] **Basic status check** — `mc case status 12345` shows running/stopped/error

### Add After Validation (v2.1)

Features to add once core workflow is proven.

- [ ] **Salesforce metadata integration** — Trigger: Users manually looking up case details. Auto-fetch case owner, severity, account
- [ ] **View container logs** — Trigger: Users asking "what happened in container?" Need `mc case logs 12345`
- [ ] **Restart container** — Trigger: Users doing stop + start manually. Add `mc case restart 12345`
- [ ] **Resource limits** — Trigger: Container consuming excessive CPU/memory. Add configurable limits
- [ ] **Start existing container** — Trigger: Users wanting to resume stopped container. Add `mc case start 12345`

### Future Consideration (v2.2+)

Features to defer until product-market fit is established.

- [ ] **Health monitoring** — Why defer: Nice to have, not critical. Wait for user reports of "zombie" containers
- [ ] **Bulk operations** — Why defer: Power user feature. Wait for users managing many cases. Build when pain point emerges
- [ ] **Case attachment to running container** — Why defer: Advanced use case. Wait for "multiple terminals per case" requests
- [ ] **Workspace mount status** — Why defer: Debugging feature. Add if users report mount issues
- [ ] **Container image versioning** — Why defer: Version pinning adds complexity. Start with single "latest" image, add versioning when image updates cause breakage
- [ ] **Shell customization injection** — Why defer: UX polish. Core workflow must work first

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Create container | HIGH | MEDIUM | P1 |
| Auto-open terminal | HIGH | HIGH | P1 |
| List all containers | HIGH | LOW | P1 |
| Stop container | HIGH | LOW | P1 |
| Delete container | HIGH | LOW | P1 |
| Execute command | HIGH | MEDIUM | P1 |
| Container image with tools | HIGH | MEDIUM | P1 |
| Workspace mounting | HIGH | LOW | P1 |
| Basic status check | MEDIUM | LOW | P1 |
| Salesforce metadata | MEDIUM | MEDIUM | P2 |
| View logs | MEDIUM | MEDIUM | P2 |
| Restart container | MEDIUM | LOW | P2 |
| Resource limits | MEDIUM | MEDIUM | P2 |
| Start existing container | MEDIUM | LOW | P2 |
| Health monitoring | LOW | MEDIUM | P3 |
| Bulk operations | LOW | MEDIUM | P3 |
| Multiple terminal attachment | LOW | LOW | P3 |
| Workspace mount status | LOW | LOW | P3 |
| Image versioning | LOW | MEDIUM | P3 |
| Shell customization | LOW | MEDIUM | P3 |

**Priority key:**
- P1: Must have for v2.0 launch (core workflow)
- P2: Should have for v2.1 (enhances core)
- P3: Nice to have for v2.2+ (polish)

## Competitor Feature Analysis

| Feature | docker-compose | kind | minikube | MC Approach |
|---------|---------------|------|----------|-------------|
| Create/Start | `up` (combined) | `create cluster` | `start` | `mc case 12345` (combined create + start + terminal attach) |
| List | `ps` (containers), `ls` (projects) | `get clusters` | `profile` (list profiles) | `mc case list` (all case containers with metadata) |
| Stop | `stop` (preserves) | N/A (delete only) | `stop` (preserves VM) | `mc case stop 12345` (preserves workspace) |
| Delete | `down` (destroys) | `delete cluster` | `delete` | `mc case delete 12345` (destroys container, keeps workspace) |
| Execute | `exec <service> <cmd>` | N/A (use kubectl) | `ssh` + `kubectl exec` | `mc case exec 12345 -- <cmd>` |
| Logs | `logs` (aggregates services) | `export logs` | `logs` | `mc case logs 12345` (container + orchestration logs) |
| Status | `ps` (list with status) | N/A (list shows all as running) | `status` (detailed) | `mc case status 12345` (detailed single case) |
| Terminal attach | `exec -it <service> sh` (manual) | N/A (kubectl after creation) | `ssh` (manual) | **Auto-opens new terminal window** (iTerm2/Terminal.app scripting) |
| Metadata | Labels (manual) | Labels (manual) | Profiles (manual naming) | **Salesforce API integration** (auto-fetch case details) |
| Multi-instance | Compose projects (multiple compose.yml) | Multiple clusters (--name flag) | Multiple profiles | **Per-case containers** (case number = container name) |

**Key Differentiators vs Competitors:**
1. **Auto-terminal attachment** — docker-compose requires manual `exec -it`, MC opens new terminal automatically
2. **Salesforce integration** — Competitors use manual labels/tags, MC auto-fetches case metadata from SF API
3. **Per-case persistence** — kind/minikube are ephemeral dev clusters, MC containers persist across sessions like case workspaces
4. **Support workflow optimization** — Competitors are general-purpose, MC is purpose-built for multi-case support engineering (5-10 concurrent cases)

## Sources

**Docker Compose:**
- [Docker Compose CLI Reference](https://docs.docker.com/reference/cli/docker/compose/) - Official Docker documentation
- [Docker Compose Lifecycle Hooks](https://docs.docker.com/compose/how-tos/lifecycle/) - Docker Docs
- [Managing Container Lifecycles with Docker Compose](https://dev.to/idsulik/managing-container-lifecycles-with-docker-compose-lifecycle-hooks-mjg) - DEV Community
- [Docker Compose Logs Guide](https://spacelift.io/blog/docker-compose-logs) - Spacelift
- [PS, List, and Inspect Commands](https://deepwiki.com/docker/compose/4.6-ps-list-and-inspect-commands) - DeepWiki

**kind (Kubernetes IN Docker):**
- [kind Quick Start](https://kind.sigs.k8s.io/docs/user/quick-start/) - Official kind documentation
- [Getting Started with Kind](https://betterstack.com/community/guides/scaling-docker/kind/) - Better Stack Community
- [kind GitHub Repository](https://github.com/kubernetes-sigs/kind) - Kubernetes SIGs

**minikube:**
- [minikube Commands Reference](https://minikube.sigs.k8s.io/docs/commands/) - Official minikube documentation (updated 2026-01-10)
- [Kubernetes Minikube: A Pragmatic 2026 Playbook](https://thelinuxcode.com/kubernetes-minikube-a-pragmatic-2026-playbook/) - TheLinuxCode
- [Exploring Minikube Commands](https://www.civo.com/academy/kubernetes-setup/exploring-minikube-commands) - Civo Academy

**devcontainer CLI:**
- [devcontainers/cli GitHub](https://github.com/devcontainers/cli) - Official reference implementation
- [Dev Container CLI Documentation](https://code.visualstudio.com/docs/devcontainers/devcontainer-cli) - VS Code Docs
- [Demystifying Dev Container Lifecycle](https://www.daytona.io/dotfiles/demystifying-the-dev-container-lifecycle-a-walkthrough) - Daytona

**Container Best Practices & Anti-Patterns:**
- [Container Anti-Patterns](https://dev.to/idsulik/container-anti-patterns-common-docker-mistakes-and-how-to-avoid-them-4129) - DEV Community (March 2025)
- [Docker Container Anti-Patterns](https://medium.com/@aishwarya.rk347/title-docker-container-anti-patterns-pitfalls-to-avoid-in-containerization-d2524b9748a0) - Medium
- [Docker Best Practices and Anti-Patterns](https://ubk.hashnode.dev/docker-best-practices-and-anti-patterns) - Hashnode
- [8 Docker Antipatterns to Stop Using](https://www.capitalone.com/tech/software-engineering/8-docker-antipatterns-to-avoid/) - Capital One Tech
- [Docker Anti Patterns](https://codefresh.io/blog/docker-anti-patterns/) - Codefresh

**Container Debugging & Inspection:**
- [Mastering Docker Debugging](https://dev.to/docker/mastering-docker-debugging-a-guide-to-docker-desktop-and-cli-tools-for-troubleshooting-containers-5a8d) - DEV Community
- [Kubernetes Basics in 2026](https://www.nucamp.co/blog/kubernetes-basics-in-2026-container-orchestration-for-backend-developers) - Nucamp
- [Mastering Docker Inspect](https://moldstud.com/articles/p-mastering-docker-inspect-advanced-techniques-for-effective-container-debugging) - MoldStud
- [Top crictl Commands for Debugging](https://dev.to/omerberatsezer/top-15-crictl-commands-with-output-debugging-kubernetes-nodes-4ao4) - DEV Community

**Container Labels & Metadata:**
- [Docker Object Labels](https://docs.docker.com/engine/manage-resources/labels/) - Official Docker documentation
- [Docker Best Practices: Tags and Labels](https://www.docker.com/blog/docker-best-practices-using-tags-and-labels-to-manage-docker-image-sprawl/) - Docker Blog
- [Docker Labels and OCI Annotations](https://snyk.io/blog/how-and-when-to-use-docker-labels-oci-container-annotations/) - Snyk
- [Mastering Docker Labels](https://dev.to/abhay_yt_52a8e72b213be229/mastering-docker-labels-for-efficient-metadata-management-3oi) - DEV Community

**Container Cleanup & Management:**
- [Remove Orphaned Containers](https://linuxhint.com/docker-remove-orphans/) - LinuxHint
- [Docker Compose Down --remove-orphans](https://dockerpros.com/wiki/docker-compose-down-remove-orphans/) - DockerPros
- [Docker Disk Usage Cleanup](https://oneuptime.com/blog/post/2026-01-06-docker-disk-usage-cleanup/view) - OneUptime (2026-01-06)
- [Clean Up Orphaned Resources in containerd](https://hexshift.medium.com/how-to-clean-up-orphaned-resources-in-containerd-safely-9d42cdc6cff9) - Medium

**Terminal Automation:**
- [iTerm2 Scripting Documentation](https://iterm2.com/documentation-scripting.html) - Official iTerm2 documentation
- [Docker Desktop Support for iTerm2](https://www.docker.com/blog/desktop-support-for-iterm2-a-feature-request-from-the-docker-public-roadmap/) - Docker Blog
- [Automate Multi-Window Experience on iTerm2](https://dev.to/vivekkodira/automate-a-multi-window-experience-on-iterm2-2j9e) - DEV Community
- [Starting Multiple App Processes in iTerm2 Tabs](https://geoffhudik.com/tech/2020/08/23/mac-starting-multiple-app-processes-in-iterm2-tabs/) - GeoffHudik.com

**Workspace Isolation Patterns:**
- [Dev Containers: Multiple Projects & Shared Config](https://dev.to/graezykev/dev-containers-part-5-multiple-projects-shared-container-configuration-2hoi) - DEV Community
- [Azure Machine Learning Workspace Concepts](https://learn.microsoft.com/en-us/azure/machine-learning/concept-workspace?view=azureml-api-2) - Microsoft Learn
- [Considerations for Multitenant Container Apps](https://learn.microsoft.com/en-us/azure/architecture/guide/multitenant/service/container-apps) - Microsoft Azure Architecture

---
*Feature research for: MC v2.0 Containerization*
*Researched: 2026-01-26*
