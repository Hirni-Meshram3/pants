# Copyright 2021 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).
from dataclasses import dataclass
from typing import Iterable, List, Type

from pants.backend.go.target_types import GoSources
from pants.core.goals.fmt import EnrichedFmtResult, LanguageFmtResults, LanguageFmtTargets
from pants.core.goals.style_request import StyleRequest
from pants.core.util_rules.source_files import SourceFiles, SourceFilesRequest
from pants.engine.fs import Digest, Snapshot
from pants.engine.internals.selectors import Get
from pants.engine.rules import collect_rules, rule
from pants.engine.unions import UnionMembership, UnionRule, union


# Note: This tracks all targets that have Go code which may be formatted by Go-related formatters.
# While gofmt is one of those, this is more generic and can work with other formatters.
@dataclass(frozen=True)
class GoLangFmtTargets(LanguageFmtTargets):
    required_fields = (GoSources,)


@union
class GoLangFmtRequest(StyleRequest):
    pass


@rule
async def format_golang_targets(
    go_fmt_targets: GoLangFmtTargets, union_membership: UnionMembership
) -> LanguageFmtResults:
    original_sources = await Get(
        SourceFiles,
        SourceFilesRequest(target[GoSources] for target in go_fmt_targets.targets),
    )
    prior_formatter_result = original_sources.snapshot

    results: List[EnrichedFmtResult] = []
    fmt_request_types: Iterable[Type[GoLangFmtRequest]] = union_membership.union_rules[
        GoLangFmtRequest
    ]
    for fmt_request_type in fmt_request_types:
        result = await Get(
            EnrichedFmtResult,
            GoLangFmtRequest,
            fmt_request_type(
                (
                    fmt_request_type.field_set_type.create(target)
                    for target in go_fmt_targets.targets
                ),
                prior_formatter_result=prior_formatter_result,
            ),
        )
        if not result.skipped:
            results.append(result)
        if result.did_change:
            prior_formatter_result = await Get(Snapshot, Digest, result.output)
    return LanguageFmtResults(
        tuple(results),
        input=original_sources.snapshot.digest,
        output=prior_formatter_result.digest,
    )


def rules():
    return [
        *collect_rules(),
        UnionRule(LanguageFmtTargets, GoLangFmtTargets),
    ]
