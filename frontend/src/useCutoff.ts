import { useSearchParams } from "react-router-dom";
import { useMeta } from "./api";
import { isCutoff } from "./format";

/** Cutoff lives in the URL (?cutoff=09:00) so a view can be shared. Default comes from the API. */
export function useCutoff() {
  const meta = useMeta();
  const [params, setParams] = useSearchParams();
  const raw = params.get("cutoff") ?? "";
  const cutoff = isCutoff(raw) ? raw : (meta.data?.default_cutoff ?? "");
  const setCutoff = (value: string) => {
    const next = new URLSearchParams(params);
    if (isCutoff(value)) next.set("cutoff", value);
    setParams(next, { replace: true });
  };
  return { cutoff, setCutoff, meta, ready: Boolean(cutoff) };
}
