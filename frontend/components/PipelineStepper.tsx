import { Icon } from "./Icon";
const STEPS: [string, string[]][] = [
  ["Research", ["RESEARCHING"]], ["Script", ["SCRIPT_GENERATED"]], ["Review", ["TECHNICAL_REVIEW"]], ["Approved", ["SCRIPT_APPROVED"]],
  ["Assets", ["ASSETS_GENERATING", "ASSETS_READY"]], ["Render", ["RENDERING"]], ["QC", ["QUALITY_CHECK"]], ["Approval", ["APPROVAL_PENDING", "APPROVED"]], ["Published", ["SCHEDULED", "PUBLISHED"]],
];
const ORDER = ["TOPIC_PENDING", "RESEARCHING", "SCRIPT_GENERATED", "TECHNICAL_REVIEW", "SCRIPT_APPROVED", "ASSETS_GENERATING", "ASSETS_READY", "RENDERING", "QUALITY_CHECK", "APPROVAL_PENDING", "APPROVED", "SCHEDULED", "PUBLISHED"];

/** Horizontal stage tracker. `last_good` marks how far the lesson got when it failed. */
export function PipelineStepper({ status, lastGood }: { status: string; lastGood?: string }) {
  const failed = status === "FAILED";
  const cur = ORDER.indexOf(failed ? lastGood ?? "TOPIC_PENDING" : status);
  return (
    <ol className="flex items-center gap-1 overflow-x-auto pb-1" aria-label="Pipeline progress">
      {STEPS.map(([name, sts], i) => {
        const idx = Math.max(...sts.map((s) => ORDER.indexOf(s)));
        const done = cur >= idx; const here = sts.includes(failed ? "" : status);
        return (
          <li key={name} className="flex items-center gap-1">
            <div className={`flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1 text-xs ring-1 ring-inset ${here ? "bg-brand-500/15 text-brand-400 ring-brand-500/40" : done ? "bg-emerald-500/10 text-emerald-300 ring-emerald-500/20" : "text-slate-500 ring-line"}`}>
              {done && !here ? <Icon name="check" className="h-3 w-3" /> : <span className={`h-1.5 w-1.5 rounded-full ${here ? "bg-brand-400" : "bg-slate-600"}`} />}{name}
            </div>
            {i < STEPS.length - 1 && <span className={`h-px w-3 ${cur > idx ? "bg-emerald-500/40" : "bg-line"}`} />}
          </li>);
      })}
      {failed && <li className="ml-2 flex items-center gap-1 whitespace-nowrap rounded-full bg-rose-500/10 px-2.5 py-1 text-xs text-rose-300 ring-1 ring-inset ring-rose-500/30"><Icon name="alert" className="h-3 w-3" />Failed after {lastGood?.toLowerCase().replace(/_/g, " ")}</li>}
    </ol>
  );
}
