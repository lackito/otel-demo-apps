# Repository and environment naming

Use `otel-demo-<responsibility>-<target>` for repositories. The shared source
repository is `otel-demo-apps`; targets are `aws` and `kind`. The word "local"
may still describe files or workstation use, but environment identities use kind.

| Responsibility | AWS | kind |
| --- | --- | --- |
| Infrastructure | otel-demo-infra-aws | otel-demo-infra-kind |
| Desired state | otel-demo-gitops-aws | otel-demo-gitops-kind |
| Source | otel-demo-apps / main | otel-demo-apps / kind |
| Argo CD Application | otel-demo-aws | otel-demo-kind |
| Cluster | otel-demo-aws-dev | otel-demo |
| kubectl context | EKS-generated context | kind-otel-demo |
| Publisher roles | otel-demo-aws-dev-<service>-github-actions | None |
| New image packages | ECR service repositories | GHCR otel-demo-kind-<service> |

`applications/otel-demo`, upstream Helm release/workload names, the
`opentelemetry-demo` namespace, and `otel-demo.localhost` identify the shared
application. Both Argo definitions explicitly set `helm.releaseName=otel-demo`
so changing the Application name cannot rename services used by Gateway routes.
They do not name a repository or delivery target. The AWS state
bucket is shared infrastructure; existing `otel-demo-infra-aws/dev/*` backend
keys already follow the naming scheme. Application repository IDs and its
main-only OIDC subject are unchanged.

## Migration order

Both environments were destroyed before this migration. These steps prepare
future deployments; no Terraform state moves are required by the repo renames.
Do not delete existing state files or the state bucket as part of renaming.

1. Review the five `refactor/environment-naming` PRs. AWS release jobs now require
   the `AWS_RELEASES_ENABLED` Actions variable to equal `true`. Leave it unset
   until AWS infrastructure and the newly named publisher roles are rebuilt.
2. In GitHub repository Settings → General, rename these repositories
   ([GitHub instructions](https://docs.github.com/en/repositories/creating-and-managing-repositories/renaming-a-repository)):
   - `otel-demo-gitops` → `otel-demo-gitops-aws`
   - `otel-demo-gitops-local` → `otel-demo-gitops-kind`
   - `otel-demo-local` → `otel-demo-infra-kind`
   Keep `otel-demo-apps` and `otel-demo-infra-aws` unchanged. Rename the two
   GitOps repositories first, then the kind infrastructure repository.
3. Update the three local folder names and their origin URLs. Keep each
   checkout's current branch and files. For SSH remotes, for example:
   `git remote set-url origin git@github.com:lackito/<new-repository-name>.git`.
   The sibling directory used by kind build scripts remains `../otel-demo-apps`.
4. In `otel-demo-apps`, configure `AWS_GITOPS_REPOSITORY_TOKEN` with Contents
   read/write for `otel-demo-gitops-aws` and `KIND_GITOPS_REPOSITORY_TOKEN` with
   Contents read/write for `otel-demo-gitops-kind`. These replace the old
   `GITOPS_REPOSITORY_TOKEN` and `LOCAL_GITOPS_REPOSITORY_TOKEN` names. Reuse
   valid token credentials after confirming repository access; do not paste
   credentials into source. Keep `GHCR_PAT` unchanged. Verify repo-scoped
   integrations and branch rules in GitHub after renaming.
5. Merge both GitOps naming PRs, then both infrastructure naming PRs, then the
   application naming PR. All five target main. No rename PR itself provisions
   resources. The AWS source change is held by the opt-in variable above.
6. Create the apps `kind` branch from the merged main commit and push it. Retain
   the old `local` branch as history until the transition is verified. Pushing a
   new branch does not reliably select all path-filtered releases, so explicitly
   dispatch the three `<service>-kind-release.yml` workflows with ref `kind`.
7. First publication creates `otel-demo-kind-recommendation`,
   `otel-demo-kind-product-catalog`, and `otel-demo-kind-ad` GHCR packages.
   Make new packages public and rerun if anonymous pull verification stops a
   release. Only successful verification promotes a new package reference.
   Inspect all three GitOps updates before recreating kind.
8. Recreate kind using `otel-demo-infra-kind` and validate cluster, platform,
   application, routing, and telemetry using its Make targets. The cluster is
   `otel-demo`; Argo watches the canonical renamed kind GitOps URL.
9. When ready for AWS, review and apply its Terraform layers, confirm publisher
   roles and token access, set `AWS_RELEASES_ENABLED=true`, and explicitly
   dispatch the three AWS workflows on main. Verify ECR digests and Argo/EKS
   rollouts. AWS downstream logging remains separate outstanding work.

## Published image compatibility

Existing kind GitOps values deliberately retain three verified, full-SHA
`otel-demo-local-*` GHCR package references. Registry packages do not become
kind-named simply because Git repositories are renamed. These pins remain valid
bootstrap artifacts until the kind workflows verify and promote real replacements.
The recommendation validator accepts these pins during the transition. New
promotions accept only `--target kind` with `otel-demo-kind-*` packages; the old
`--target local` interface is retired. Remove bootstrap compatibility after all
three replacements have been verified. Do not substitute unpublished image names.

## Validation boundary

Static checks and container CI can run before GitHub renames. Checkout/promotion
against the new GitOps names, new package visibility, and recreated-cluster
validation must be checked after the external rename. Historical documentation
may link old workflow runs; runtime URLs use the canonical repository names.
