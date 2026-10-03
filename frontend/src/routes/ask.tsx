import { FormEvent, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, RotateCcw, Send, X } from "lucide-react";
import {
  askAdvisor,
  createIntakeSource,
  fetchIntakeSource,
  fetchIntakeSources,
  retryIntakeSource,
  reviewIntakeProposal,
  type AdvisorAnswer,
  type IntakeSourceType,
} from "@/lib/api";
import { PageHeader, Panel } from "@/components/dashboard/page-header";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

export const Route = createFileRoute("/ask")({
  head: () => ({ meta: [{ title: "VP Advisor — ColorStack AI" }] }),
  component: AdvisorPage,
});

const sourceTypes: Array<{ value: IntakeSourceType; label: string }> = [
  { value: "conversation", label: "Conversation" },
  { value: "meeting_notes", label: "Meeting notes" },
  { value: "email", label: "Email" },
  { value: "document", label: "Document" },
  { value: "transcript", label: "Transcript" },
  { value: "general_note", label: "General note" },
];

function AdvisorResponse({ result }: { result: AdvisorAnswer }) {
  if (!result.answer) {
    return (
      <div className="space-y-1 text-[12.5px] text-muted-foreground">
        {result.warnings.map((warning) => (
          <p key={warning}>{warning}</p>
        ))}
      </div>
    );
  }
  return (
    <div className="space-y-4 text-[12.5px]">
      <p className="leading-relaxed">{result.answer.summary}</p>
      <div>
        <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
          What you should do
        </p>
        <ol className="space-y-2">
          {result.answer.priorities.map((action, index) => (
            <li key={`${action.title}-${index}`} className="flex gap-2">
              <span className="text-muted-foreground">{index + 1}.</span>
              <div>
                <p className="font-medium">{action.title}</p>
                <p className="text-muted-foreground">{action.reason}</p>
              </div>
            </li>
          ))}
        </ol>
      </div>
      {result.answer.uncertainty.length > 0 && (
        <div>
          <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
            Questions and uncertainty
          </p>
          {result.answer.uncertainty.map((item) => (
            <p key={item}>• {item}</p>
          ))}
        </div>
      )}
    </div>
  );
}

function AdvisorPage() {
  const client = useQueryClient();
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<AdvisorAnswer | null>(null);
  const [title, setTitle] = useState("");
  const [sourceType, setSourceType] = useState<IntakeSourceType>("conversation");
  const [content, setContent] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const sources = useQuery({
    queryKey: ["intake-sources"],
    queryFn: fetchIntakeSources,
    refetchInterval: 5000,
  });
  const selected = useQuery({
    queryKey: ["intake-source", selectedId],
    queryFn: () => fetchIntakeSource(selectedId!),
    enabled: selectedId !== null,
    refetchInterval: selectedId ? 5000 : false,
  });
  const ask = useMutation({ mutationFn: askAdvisor, onSuccess: setAnswer });
  const submit = useMutation({
    mutationFn: createIntakeSource,
    onSuccess: (source) => {
      setTitle("");
      setContent("");
      setSelectedId(source.id);
      void client.invalidateQueries({ queryKey: ["intake-sources"] });
    },
  });
  const review = useMutation({
    mutationFn: ({ id, status }: { id: string; status: "approved" | "rejected" }) =>
      reviewIntakeProposal(id, status),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["intake-source", selectedId] });
      void client.invalidateQueries({ queryKey: ["intake-sources"] });
    },
  });
  const retry = useMutation({
    mutationFn: retryIntakeSource,
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["intake-source", selectedId] });
      void client.invalidateQueries({ queryKey: ["intake-sources"] });
    },
  });

  function askQuestion(event: FormEvent) {
    event.preventDefault();
    if (question.trim()) ask.mutate(question.trim());
  }

  function addSource(event: FormEvent) {
    event.preventDefault();
    if (title.trim() && content.trim()) {
      submit.mutate({ title: title.trim(), source_type: sourceType, content: content.trim() });
    }
  }

  return (
    <>
      <PageHeader
        title="VP Advisor"
        subtitle="Ask what to do, add context, and review what the AI believes it learned"
      />
      <Panel
        title="Ask ColorStack AI"
        description="Uses bounded organizational context and approved inbox facts"
      >
        <form onSubmit={askQuestion} className="space-y-2">
          <div className="flex gap-2">
            <Input
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="What needs my attention today?"
            />
            <Button type="submit" size="sm" disabled={ask.isPending || !question.trim()}>
              <Send /> Ask
            </Button>
          </div>
          {ask.error && <p className="text-xs text-destructive">{ask.error.message}</p>}
          {ask.isPending && (
            <p className="text-xs text-muted-foreground">Reasoning over current context…</p>
          )}
          {answer && <AdvisorResponse result={answer} />}
        </form>
      </Panel>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <Panel
          title="Add to VP Inbox"
          description="Stored locally; extracted facts require your approval"
        >
          <form onSubmit={addSource} className="space-y-3">
            <div className="grid gap-2 sm:grid-cols-[1fr_180px]">
              <Input
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="Source title"
              />
              <select
                value={sourceType}
                onChange={(event) => setSourceType(event.target.value as IntakeSourceType)}
                className="h-9 rounded-md border border-input bg-background px-3 text-sm"
              >
                {sourceTypes.map((type) => (
                  <option key={type.value} value={type.value}>
                    {type.label}
                  </option>
                ))}
              </select>
            </div>
            <Textarea
              value={content}
              onChange={(event) => setContent(event.target.value)}
              placeholder="Paste a conversation, meeting notes, email, transcript, or document text…"
              className="min-h-48"
            />
            <div className="flex items-center justify-between gap-3">
              <p className="text-[11.5px] text-muted-foreground">
                Nothing becomes trusted context until you approve it.
              </p>
              <Button
                type="submit"
                size="sm"
                disabled={submit.isPending || !title.trim() || !content.trim()}
              >
                Add source
              </Button>
            </div>
            {submit.error && <p className="text-xs text-destructive">{submit.error.message}</p>}
          </form>
        </Panel>

        <Panel title="Recent sources" bodyClassName="">
          {sources.isPending ? (
            <p className="p-3 text-xs text-muted-foreground">Loading inbox…</p>
          ) : (
            <ul>
              {(sources.data ?? []).map((source) => (
                <li key={source.id}>
                  <button
                    type="button"
                    onClick={() => setSelectedId(source.id)}
                    className="w-full border-b border-border/70 px-3 py-2 text-left hover:bg-accent"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate text-[12.5px] font-medium">{source.title}</span>
                      <Badge variant="outline">{source.status}</Badge>
                    </div>
                    <p className="mt-0.5 text-[11px] text-muted-foreground">
                      {source.proposal_count} proposals · {source.pending_count} awaiting review
                    </p>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      {selected.data && (
        <Panel
          title={selected.data.title}
          description={`${selected.data.source_type.replaceAll("_", " ")} · ${selected.data.status}`}
          actions={
            selected.data.status === "failed" ? (
              <Button size="sm" variant="outline" onClick={() => retry.mutate(selected.data!.id)}>
                <RotateCcw /> Retry
              </Button>
            ) : undefined
          }
          bodyClassName=""
        >
          {selected.data.error && (
            <p className="border-b border-border p-3 text-xs text-destructive">
              {selected.data.error}
            </p>
          )}
          {selected.data.proposals.length === 0 ? (
            <p className="p-3 text-xs text-muted-foreground">
              {selected.data.status === "processed"
                ? "No organizational facts found."
                : "Waiting for local extraction."}
            </p>
          ) : (
            <ul>
              {selected.data.proposals.map((proposal) => {
                const fact = proposal.fact;
                const description = fact.task || fact.value || fact.event_name || fact.type;
                return (
                  <li
                    key={proposal.id}
                    className="flex items-start gap-3 border-b border-border/70 px-3 py-3"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline">{fact.type.replaceAll("_", " ")}</Badge>
                        <Badge variant="outline">{proposal.status}</Badge>
                        <span className="text-[11px] text-muted-foreground">
                          {Math.round(fact.confidence * 100)}% confidence
                        </span>
                      </div>
                      <p className="mt-1.5 text-[12.5px] font-medium">{description}</p>
                      <p className="text-[11.5px] text-muted-foreground">
                        {[fact.event_name, fact.owner_name, fact.deadline_text]
                          .filter(Boolean)
                          .join(" · ")}
                      </p>
                    </div>
                    {proposal.status === "pending" && (
                      <div className="flex gap-1">
                        <Button
                          size="icon"
                          variant="outline"
                          aria-label="Approve"
                          onClick={() => review.mutate({ id: proposal.id, status: "approved" })}
                        >
                          <Check />
                        </Button>
                        <Button
                          size="icon"
                          variant="outline"
                          aria-label="Reject"
                          onClick={() => review.mutate({ id: proposal.id, status: "rejected" })}
                        >
                          <X />
                        </Button>
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>
      )}
    </>
  );
}
