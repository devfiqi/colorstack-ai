import logging

from colorstack_ai.state.ambiguity import AmbiguityResolver
from colorstack_ai.state.models import (
    ReconciliationSummary,
    RunStatus,
    StateProposal,
)
from colorstack_ai.state.policy import proposals_for_fact
from colorstack_ai.state.repository import StateRepository
from colorstack_ai.state.resolution import EntityResolver

logger = logging.getLogger(__name__)


class StateProcessor:
    def __init__(
        self,
        *,
        repository: StateRepository,
        resolver: EntityResolver,
        ambiguity_resolver: AmbiguityResolver | None = None,
    ) -> None:
        self._repository = repository
        self._resolver = resolver
        self._ambiguity_resolver = ambiguity_resolver

    async def process(
        self,
        *,
        mode: str,
        limit: int | None,
    ) -> ReconciliationSummary:
        if mode == "rebuild":
            await self._repository.reset_derived_state()

        run_id = await self._repository.create_run(mode)
        summary = ReconciliationSummary()
        try:
            facts = await self._repository.candidate_facts(
                mode=mode,
                limit=limit,
            )
            logger.info("Scanning %s extracted facts", len(facts))

            for index, fact in enumerate(facts, start=1):
                summary.scanned += 1
                await self._repository.mark_processing(fact.id, run_id)
                try:
                    resolution = await self._resolver.resolve(fact)
                    if resolution is None:
                        await self._repository.mark_unresolved(
                            fact_id=fact.id,
                            run_id=run_id,
                            reason="entity could not be resolved safely",
                            candidate_data={
                                "event_name": fact.event_name,
                                "task": fact.task,
                                "guild_id": fact.guild_id,
                            },
                        )
                        summary.deferred += 1
                        continue

                    proposals = proposals_for_fact(
                        fact,
                        resolution.entity_type,
                    )
                    if (
                        not proposals
                        and fact.fact_type != "event_mention"
                        and self._ambiguity_resolver is not None
                    ):
                        response, raw = (
                            await self._ambiguity_resolver.interpret(
                                fact,
                                resolution,
                            )
                        )
                        if response.proposal is not None:
                            candidate = response.proposal
                            if candidate.entity_type != resolution.entity_type:
                                await self._repository.mark_unresolved(
                                    fact_id=fact.id,
                                    run_id=run_id,
                                    reason=(
                                        "model proposal changed the resolved "
                                        "entity type"
                                    ),
                                    proposed_interpretation=raw,
                                )
                                summary.deferred += 1
                                continue
                            proposals = [
                                StateProposal(
                                    entity_type=candidate.entity_type,
                                    field=candidate.field,
                                    value=candidate.value,
                                    change_type=candidate.change_type,
                                    reason=(
                                        "validated local-model proposal: "
                                        f"{candidate.reason}"
                                    ),
                                    reconciliation_confidence=min(
                                        fact.confidence,
                                        candidate.confidence,
                                    ),
                                )
                            ]

                    if not proposals and fact.fact_type != "event_mention":
                        await self._repository.mark_unresolved(
                            fact_id=fact.id,
                            run_id=run_id,
                            reason="fact has no deterministic state mapping",
                        )
                        summary.deferred += 1
                        continue

                    applied, _ = await self._repository.apply_fact(
                        fact=fact,
                        run_id=run_id,
                        resolution=resolution,
                        proposals=proposals,
                    )
                    if applied:
                        summary.applied += 1
                    else:
                        summary.no_change += 1
                except Exception as error:
                    logger.exception(
                        "Failed to reconcile fact %s",
                        fact.id,
                    )
                    await self._repository.mark_failed(
                        fact_id=fact.id,
                        run_id=run_id,
                        error=str(error),
                    )
                    summary.failed += 1

                if index % 100 == 0:
                    logger.info(
                        "Reconciled %s/%s facts (%s applied, %s deferred)",
                        index,
                        len(facts),
                        summary.applied,
                        summary.deferred,
                    )

            await self._repository.finish_run(
                run_id=run_id,
                status=RunStatus.SUCCESS,
                summary=summary,
            )
        except Exception as error:
            await self._repository.finish_run(
                run_id=run_id,
                status=RunStatus.FAILED,
                summary=summary,
                error=str(error),
            )
            raise

        logger.info(
            "Reconciliation complete: scanned=%s applied=%s deferred=%s "
            "no_change=%s failed=%s",
            summary.scanned,
            summary.applied,
            summary.deferred,
            summary.no_change,
            summary.failed,
        )
        return summary
