# Application branching

Use feature branches for development, `kind` for local releases, and `main` for
reviewed AWS releases. Infrastructure and GitOps repositories use `main` for
their own environment; they do not need a `kind` release branch.

## Normal workflow

1. Create a feature branch from updated `main` and commit the change.
2. Merge the feature into `kind` and push to test it locally.
3. Check the release job, image, rollout, application behavior, and telemetry.
4. Open a PR from the feature branch into `main`. Review and merge it when ready.
5. Merge updated `main` into `kind` when it contains changes kind has not received.

Example for Product Catalog; use the same process for Ad or Recommendation:

```bash
git fetch origin
git switch main
git pull --ff-only
git switch -c feature/catalog-change
# Edit the service, then commit the intended files.
git add apps/product-catalog/
git commit -m "feat(catalog): describe the change"

git switch kind
git pull --ff-only
git merge feature/catalog-change
git push origin kind
# Wait for the release and test the application.

git push -u origin feature/catalog-change
# Open a PR from feature/catalog-change into main.
```

CI runs for pull requests and pushes to `main` or `kind`. Pushing a feature
branch alone does not run the current CI or release workflows. A merge into
`main` can release matching services when `AWS_RELEASES_ENABLED=true`.

## Keeping kind current

Merging main into kind does not apply the same feature twice. It brings in
other reviewed fixes or changes made during PR review. If both branches already
contain the same code, the merge may only align their histories.

```bash
git fetch origin
git switch kind
git pull --ff-only
git merge origin/main -m "Merge main into kind to sync reviewed changes"
git push origin kind
```

If Git reports `Already up to date`, nothing more is needed. A fast-forward
uses existing commits and does not use the merge message. If conflicts occur,
resolve and review them before committing. Do not merge unrelated kind
experiments into main simply to clear GitHub's ahead/behind counter.

## Testing a workflow without code changes

In Actions, select the desired service's **Release ... service to kind** workflow
and manually run it on `kind`. For AWS, select the AWS workflow and `main`.
Creating or synchronizing a branch does not guarantee an image release: the
workflows use path filters.

Kind and AWS build images separately. Compare each release's SHA tag and image
digest with the running pod; they are not the same image promoted between registries.
