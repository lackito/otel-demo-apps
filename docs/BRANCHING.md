# Application branching and release strategy

This strategy applies to `otel-demo-apps`. Both infrastructure repositories and
both GitOps repositories use `main` for their own environment; they do not need
an application-style `kind` release branch.

| Application branch | Purpose | Release behavior |
| --- | --- | --- |
| Feature branch, such as `feature/catalog-reload` | Develop and review one change | No image release from a feature-branch push |
| `kind` | Integrate changes for local validation | Matching source/workflow changes publish to GHCR and promote kind GitOps |
| `main` | Reviewed source for AWS | Matching changes publish to ECR and promote AWS GitOps when `AWS_RELEASES_ENABLED=true` |

CI runs for pull requests and pushes to `main` or `kind`. A feature-branch push
alone does not trigger the current CI workflow. Creating a PR does not release
an AWS image; merging it into enabled `main` can.

## Development routine

1. Create a feature branch from updated `main` and commit the change.
2. Merge that feature branch into updated `kind` and push `kind` to test it.
3. Verify the release run, GitOps image update, Argo rollout, application
   behavior, traces, metrics, and logs.
4. Push the feature branch and open a PR from it into `main`. Merge the PR
   after review and CI. Keep unrelated kind experiments out of that PR.
5. Bring `main` into `kind` when `main` has changes or merge results that
   `kind` does not yet contain. This keeps local testing aligned with reviewed
   source. It does not apply the same feature twice, and is not mandatory after
   every feature when there is nothing new to synchronize.

Example, starting in the application repository:

```bash
git fetch origin
git switch main
git pull --ff-only
git switch -c feature/catalog-reload
# Edit and commit the intended files.
git add apps/product-catalog/
git commit -m "feat(catalog): describe the actual change"

git switch kind
git pull --ff-only
git merge feature/catalog-reload
git push origin kind
# Wait for CI/release and validate the running application and telemetry.

git push -u origin feature/catalog-reload
# Open a PR: feature/catalog-reload -> main.
```

After the PR is merged, synchronize reviewed main changes into kind as needed:

```bash
git fetch origin
git switch kind
git pull --ff-only
git merge origin/main
# If conflicts occur, resolve and review them before committing/pushing.
git push origin kind
```

`git pull --ff-only` stops if the local checkout has diverged from its remote;
inspect and reconcile those changes rather than resetting or force-pushing.

## Why synchronize main after the feature reached both branches?

If both branches contain the exact same feature change, step 5 is not needed to
add that feature again. It is a synchronization step for the branches as a whole.

For example, both branches may already contain your Product Catalog change.
Meanwhile, a separate PR adds a Recommendation fix to `main`. Merging
`origin/main` into `kind` brings that Recommendation fix into the local test
environment. The next feature is then tested alongside the reviewed fix.

The two merges can also have different results: review may amend a feature
before it reaches `main`, or its main merge may resolve a conflict differently.
Synchronizing brings those reviewed results into `kind` too. Review any conflicts
against both the intended feature and existing kind-only experiments.

Separate merges create different merge commits even when the resulting files
are identical. A squash merge also gives main a different commit identity.
GitHub's ahead/behind counts describe commit ancestry, not just code differences.
A merge from main can record shared history without changing application files.
Do not merge kind experiments into main merely to clear an ahead counter.

If main contains only a different merge commit and the application files already
match, synchronization is useful for history but does not add new functionality.
If main is already an ancestor of kind, `git merge origin/main` reports
`Already up to date`. There is no need to manufacture another merge.

## Release boundaries

A service-only change normally releases only that service. Shared files such as
`scripts/promote.py` can trigger multiple service workflows. A main-to-kind
merge may run CI without starting a release if no release path-filtered files
changed. For a no-code release test, manually dispatch the relevant kind workflow
with branch `kind` selected rather than creating a dummy change.

The two targets currently build images independently. Testing a kind image does
not promote that exact image digest to AWS; AWS builds and verifies its own image
from the main commit. Compare release SHA tags and, for exact content, image
digests against the running pods.
