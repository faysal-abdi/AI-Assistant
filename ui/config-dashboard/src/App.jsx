import { useEffect, useMemo, useState } from "react";
import {
  useMutation,
  useQuery,
  useQueryClient
} from "@tanstack/react-query";
import {
  fetchConfig,
  fetchPreferences,
  fetchSafetyLog,
  fetchToolingConsent,
  patchSection,
  setPreference,
  updateConfig
} from "./api/client.js";
import { SectionCard } from "./components/SectionCard.jsx";

function LoadingState() {
  return (
    <div className="app-shell">
      <div className="card">
        <h2>Loading configuration…</h2>
        <p>Please ensure the config service is running.</p>
      </div>
    </div>
  );
}

function ErrorState({ error }) {
  return (
    <div className="app-shell">
      <div className="card">
        <h2>Service unavailable</h2>
        <p>{error?.message ?? "Unable to reach the configuration service."}</p>
      </div>
    </div>
  );
}

const splitLines = (value) =>
  value
    .split(/[\n,]/)
    .map((entry) => entry.trim())
    .filter(Boolean);

export default function App() {
  const queryClient = useQueryClient();

  const {
    data: config,
    isLoading,
    isError,
    error,
    dataUpdatedAt
  } = useQuery({
    queryKey: ["config"],
    queryFn: fetchConfig
  });

  const updateMutation = useMutation({
    mutationFn: updateConfig,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["config"] })
  });

  const patchMutation = useMutation({
    mutationFn: patchSection,
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["config"] });
      if (variables?.section === "tooling") {
        queryClient.invalidateQueries({ queryKey: ["tooling-consent"] });
      }
    }
  });

  const [generalState, setGeneralState] = useState({
    loop_rate_hz: "",
    perception_latency: "",
    planning_horizon: "",
    control_margin: ""
  });

  const [modelsState, setModelsState] = useState({});
  const [retrievalState, setRetrievalState] = useState({});
  const [toolingState, setToolingState] = useState({});
  const [voiceState, setVoiceState] = useState({});
  const [memoryState, setMemoryState] = useState({});
  const [safetyState, setSafetyState] = useState({});

  useEffect(() => {
    if (!config) return;
    setGeneralState({
      loop_rate_hz: config.loop_rate_hz ?? "",
      perception_latency: config.perception?.latency_budget_ms ?? "",
      planning_horizon: config.planning?.horizon_s ?? "",
      control_margin: config.control?.safety_margin ?? ""
    });
    setModelsState({ ...config.models });
    setRetrievalState({ ...config.retrieval });
    setToolingState({
      ...config.tooling,
      shell_allowlist_text: (config.tooling?.shell_allowlist ?? []).join("\n"),
      file_search_roots_text: (config.tooling?.file_search_roots ?? []).join("\n")
    });
    setVoiceState({ ...config.voice });
    setMemoryState({ ...config.memory });
    setSafetyState({ ...config.safety });
  }, [config]);

  const [sessionId, setSessionId] = useState("default");
  const [preferenceDraft, setPreferenceDraft] = useState({ key: "", value: "" });

  const {
    data: preferences = {},
    isFetching: loadingPreferences,
    refetch: refetchPreferences
  } = useQuery({
    queryKey: ["preferences", sessionId],
    queryFn: () => fetchPreferences(sessionId),
    enabled: Boolean(sessionId)
  });

  const preferenceMutation = useMutation({
    mutationFn: setPreference,
    onSuccess: () => refetchPreferences()
  });

  const {
    data: safetyLog = [],
    refetch: refetchSafetyLog,
    isFetching: loadingSafetyLog
  } = useQuery({
    queryKey: ["safety-log"],
    queryFn: () => fetchSafetyLog(150),
    staleTime: 30_000
  });

  const { data: toolingConsent } = useQuery({
    queryKey: ["tooling-consent"],
    queryFn: fetchToolingConsent
  });

  if (isLoading) {
    return <LoadingState />;
  }

  if (isError) {
    return <ErrorState error={error} />;
  }

  const lastSynced = useMemo(() => {
    if (!dataUpdatedAt) {
      return "just now";
    }
    const delta = Date.now() - dataUpdatedAt;
    const seconds = Math.round(delta / 1000);
    if (seconds < 5) return "just now";
    if (seconds < 60) return `${seconds}s ago`;
    const minutes = Math.round(seconds / 60);
    return `${minutes}m ago`;
  }, [dataUpdatedAt]);

  const handleGeneralSave = () => {
    const next = JSON.parse(JSON.stringify(config));
    next.loop_rate_hz = Number(generalState.loop_rate_hz) || 0;
    next.perception = {
      ...next.perception,
      latency_budget_ms: Number(generalState.perception_latency) || 0
    };
    next.planning = {
      ...next.planning,
      horizon_s: Number(generalState.planning_horizon) || 0
    };
    next.control = {
      ...next.control,
      safety_margin: Number(generalState.control_margin) || 0
    };
    updateMutation.mutate(next);
  };

  const handleModelsSave = () => {
    const payload = {
      ...modelsState,
      temperature: Number(modelsState.temperature),
      max_output_tokens: Number(modelsState.max_output_tokens)
    };
    patchMutation.mutate({ section: "models", payload });
  };

  const handleRetrievalSave = () => {
    const payload = {
      ...retrievalState,
      top_k: Number(retrievalState.top_k),
      lexical_weight: Number(retrievalState.lexical_weight),
      vector_weight: Number(retrievalState.vector_weight),
      min_score: Number(retrievalState.min_score)
    };
    patchMutation.mutate({ section: "retrieval", payload });
  };

  const handleToolingSave = () => {
    const payload = {
      auto_search: Boolean(toolingState.auto_search),
      max_tool_time_ms: Number(toolingState.max_tool_time_ms),
      allow_control_commands: Boolean(toolingState.allow_control_commands),
      allow_shell_commands: Boolean(toolingState.allow_shell_commands),
      shell_allowlist: splitLines(toolingState.shell_allowlist_text ?? ""),
      file_search_roots: splitLines(toolingState.file_search_roots_text ?? ""),
      enable_calendar_tools: Boolean(toolingState.enable_calendar_tools),
      enable_email_tools: Boolean(toolingState.enable_email_tools),
      enable_home_automation: Boolean(toolingState.enable_home_automation)
    };
    patchMutation.mutate({ section: "tooling", payload });
  };

  const handleVoiceSave = () => {
    const payload = {
      ...voiceState,
      use_wake_word: Boolean(voiceState.use_wake_word),
      enable_tts: Boolean(voiceState.enable_tts)
    };
    patchMutation.mutate({ section: "voice", payload });
  };

  const handleMemorySave = () => {
    const payload = {
      db_path: memoryState.db_path,
      history_window: Number(memoryState.history_window)
    };
    patchMutation.mutate({ section: "memory", payload });
  };

  const handleSafetySave = () => {
    const payload = {
      default_privilege: safetyState.default_privilege,
      audit_log_path: safetyState.audit_log_path,
      pause_on_start: Boolean(safetyState.pause_on_start)
    };
    patchMutation.mutate({ section: "safety", payload });
  };

  const handlePreferenceSubmit = (event) => {
    event.preventDefault();
    if (!preferenceDraft.key || sessionId.trim() === "") {
      return;
    }
    preferenceMutation.mutate({
      sessionId,
      key: preferenceDraft.key,
      value: preferenceDraft.value
    });
    setPreferenceDraft({ key: "", value: "" });
  };

  return (
    <div className="app-shell">
      <header className="status-bar">
        <div>
          <strong>Robot Assistant Configuration</strong>
          <div>Update runtime cadence, tooling guardrails, and voice preferences.</div>
        </div>
        <span className="pill">Synced {lastSynced}</span>
      </header>

      <SectionCard
        title="Runtime Loop"
        description="Adjust control loop cadence and planner/perception budgets."
        footer={
          <button onClick={handleGeneralSave} disabled={updateMutation.isLoading}>
            {updateMutation.isLoading ? "Saving…" : "Save"}
          </button>
        }
      >
        <div>
          <label htmlFor="loop_rate_hz">Loop Rate (Hz)</label>
          <input
            id="loop_rate_hz"
            type="number"
            min="1"
            step="0.1"
            value={generalState.loop_rate_hz}
            onChange={(event) =>
              setGeneralState((prev) => ({ ...prev, loop_rate_hz: event.target.value }))
            }
          />
        </div>
        <div>
          <label htmlFor="perception_latency">Perception Budget (ms)</label>
          <input
            id="perception_latency"
            type="number"
            value={generalState.perception_latency}
            onChange={(event) =>
              setGeneralState((prev) => ({ ...prev, perception_latency: event.target.value }))
            }
          />
        </div>
        <div>
          <label htmlFor="planning_horizon">Planning Horizon (s)</label>
          <input
            id="planning_horizon"
            type="number"
            value={generalState.planning_horizon}
            onChange={(event) =>
              setGeneralState((prev) => ({ ...prev, planning_horizon: event.target.value }))
            }
          />
        </div>
        <div>
          <label htmlFor="control_margin">Control Safety Margin</label>
          <input
            id="control_margin"
            type="number"
            step="0.01"
            value={generalState.control_margin}
            onChange={(event) =>
              setGeneralState((prev) => ({ ...prev, control_margin: event.target.value }))
            }
          />
        </div>
      </SectionCard>

      <SectionCard
        title="Model Routing"
        description="Balance speed versus quality by tuning default allocations."
        footer={
          <button onClick={handleModelsSave} disabled={patchMutation.isLoading}>
            {patchMutation.isLoading ? "Saving…" : "Save"}
          </button>
        }
      >
        <div>
          <label htmlFor="default_model">Default Model</label>
          <input
            id="default_model"
            value={modelsState.default_model ?? ""}
            onChange={(event) =>
              setModelsState((prev) => ({ ...prev, default_model: event.target.value }))
            }
          />
        </div>
        <div>
          <label htmlFor="fast_model">Fast Model</label>
          <input
            id="fast_model"
            value={modelsState.fast_model ?? ""}
            onChange={(event) =>
              setModelsState((prev) => ({ ...prev, fast_model: event.target.value }))
            }
          />
        </div>
        <div>
          <label htmlFor="offline_model">Offline Model</label>
          <input
            id="offline_model"
            value={modelsState.offline_model ?? ""}
            onChange={(event) =>
              setModelsState((prev) => ({ ...prev, offline_model: event.target.value }))
            }
          />
        </div>
        <div>
          <label htmlFor="temperature">Temperature</label>
          <input
            id="temperature"
            type="number"
            step="0.05"
            value={modelsState.temperature ?? 0}
            onChange={(event) =>
              setModelsState((prev) => ({ ...prev, temperature: event.target.value }))
            }
          />
        </div>
        <div>
          <label htmlFor="max_tokens">Max Output Tokens</label>
          <input
            id="max_tokens"
            type="number"
            value={modelsState.max_output_tokens ?? 0}
            onChange={(event) =>
              setModelsState((prev) => ({ ...prev, max_output_tokens: event.target.value }))
            }
          />
        </div>
      </SectionCard>

      <SectionCard
        title="Retrieval Settings"
        description="Control hybrid search blend and minimum relevance score."
        footer={
          <button onClick={handleRetrievalSave} disabled={patchMutation.isLoading}>
            {patchMutation.isLoading ? "Saving…" : "Save"}
          </button>
        }
        layout="two"
      >
        <div>
          <label htmlFor="top_k">Top K</label>
          <input
            id="top_k"
            type="number"
            value={retrievalState.top_k ?? 0}
            onChange={(event) =>
              setRetrievalState((prev) => ({ ...prev, top_k: event.target.value }))
            }
          />
        </div>
        <div>
          <label htmlFor="lexical_weight">Lexical Weight</label>
          <input
            id="lexical_weight"
            type="number"
            step="0.05"
            value={retrievalState.lexical_weight ?? 0}
            onChange={(event) =>
              setRetrievalState((prev) => ({ ...prev, lexical_weight: event.target.value }))
            }
          />
        </div>
        <div>
          <label htmlFor="vector_weight">Vector Weight</label>
          <input
            id="vector_weight"
            type="number"
            step="0.05"
            value={retrievalState.vector_weight ?? 0}
            onChange={(event) =>
              setRetrievalState((prev) => ({ ...prev, vector_weight: event.target.value }))
            }
          />
        </div>
        <div>
          <label htmlFor="min_score">Min Score</label>
          <input
            id="min_score"
            type="number"
            step="0.01"
            value={retrievalState.min_score ?? 0}
            onChange={(event) =>
              setRetrievalState((prev) => ({ ...prev, min_score: event.target.value }))
            }
          />
        </div>
      </SectionCard>

      <SectionCard
        title="Tooling & Guardrails"
        description="Configure which tools are available and the consent expectations."
        footer={
          <button onClick={handleToolingSave} disabled={patchMutation.isLoading}>
            {patchMutation.isLoading ? "Saving…" : "Save"}
          </button>
        }
      >
        <div>
          <label htmlFor="auto_search">Auto Search</label>
          <select
            id="auto_search"
            value={toolingState.auto_search ? "true" : "false"}
            onChange={(event) =>
              setToolingState((prev) => ({ ...prev, auto_search: event.target.value === "true" }))
            }
          >
            <option value="true">Enabled</option>
            <option value="false">Disabled</option>
          </select>
        </div>
        <div>
          <label htmlFor="max_tool_time_ms">Max Tool Time (ms)</label>
          <input
            id="max_tool_time_ms"
            type="number"
            value={toolingState.max_tool_time_ms ?? 0}
            onChange={(event) =>
              setToolingState((prev) => ({ ...prev, max_tool_time_ms: event.target.value }))
            }
          />
        </div>
        <div>
          <label htmlFor="allow_control">Allow Control Commands</label>
          <select
            id="allow_control"
            value={toolingState.allow_control_commands ? "true" : "false"}
            onChange={(event) =>
              setToolingState((prev) => ({
                ...prev,
                allow_control_commands: event.target.value === "true"
              }))
            }
          >
            <option value="false">Disabled</option>
            <option value="true">Enabled</option>
          </select>
        </div>
        <div>
          <label htmlFor="allow_shell">Allow Shell Commands</label>
          <select
            id="allow_shell"
            value={toolingState.allow_shell_commands ? "true" : "false"}
            onChange={(event) =>
              setToolingState((prev) => ({
                ...prev,
                allow_shell_commands: event.target.value === "true"
              }))
            }
          >
            <option value="false">Disabled</option>
            <option value="true">Enabled</option>
          </select>
        </div>
        <div>
          <label htmlFor="allow_calendar">Calendar Tools</label>
          <select
            id="allow_calendar"
            value={toolingState.enable_calendar_tools ? "true" : "false"}
            onChange={(event) =>
              setToolingState((prev) => ({
                ...prev,
                enable_calendar_tools: event.target.value === "true"
              }))
            }
          >
            <option value="false">Disabled</option>
            <option value="true">Enabled</option>
          </select>
        </div>
        <div>
          <label htmlFor="allow_email">Email Tools</label>
          <select
            id="allow_email"
            value={toolingState.enable_email_tools ? "true" : "false"}
            onChange={(event) =>
              setToolingState((prev) => ({
                ...prev,
                enable_email_tools: event.target.value === "true"
              }))
            }
          >
            <option value="false">Disabled</option>
            <option value="true">Enabled</option>
          </select>
        </div>
        <div>
          <label htmlFor="allow_home">Home Automation</label>
          <select
            id="allow_home"
            value={toolingState.enable_home_automation ? "true" : "false"}
            onChange={(event) =>
              setToolingState((prev) => ({
                ...prev,
                enable_home_automation: event.target.value === "true"
              }))
            }
          >
            <option value="false">Disabled</option>
            <option value="true">Enabled</option>
          </select>
        </div>
        <div style={{ gridColumn: "1 / -1" }}>
          <label htmlFor="shell_allowlist">Shell Allowlist</label>
          <textarea
            id="shell_allowlist"
            rows={3}
            value={toolingState.shell_allowlist_text ?? ""}
            onChange={(event) =>
              setToolingState((prev) => ({
                ...prev,
                shell_allowlist_text: event.target.value
              }))
            }
          />
          <small>Separate entries with commas or new lines.</small>
        </div>
        <div style={{ gridColumn: "1 / -1" }}>
          <label htmlFor="file_roots">File Search Roots</label>
          <textarea
            id="file_roots"
            rows={3}
            value={toolingState.file_search_roots_text ?? ""}
            onChange={(event) =>
              setToolingState((prev) => ({
                ...prev,
                file_search_roots_text: event.target.value
              }))
            }
          />
        </div>
        {toolingConsent ? (
          <div style={{ gridColumn: "1 / -1" }}>
            <label>Consent Matrix</label>
            <table className="table">
              <thead>
                <tr>
                  <th>Tool</th>
                  <th>Consent</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {toolingConsent.consent_matrix.map((row) => (
                  <tr key={row.tool}>
                    <td>{row.tool}</td>
                    <td>{row.requires_consent ? "Required" : "Auto"}</td>
                    <td>{row.enabled ? "Enabled" : "Disabled"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </SectionCard>

      <SectionCard
        title="Voice Experience"
        description="Tune wake word, transcription locale, and speech synthesis voice."
        footer={
          <button onClick={handleVoiceSave} disabled={patchMutation.isLoading}>
            {patchMutation.isLoading ? "Saving…" : "Save"}
          </button>
        }
      >
        <div>
          <label htmlFor="wake_word">Wake Word</label>
          <input
            id="wake_word"
            value={voiceState.wake_word ?? ""}
            onChange={(event) =>
              setVoiceState((prev) => ({ ...prev, wake_word: event.target.value }))
            }
          />
        </div>
        <div>
          <label htmlFor="use_wake_word">Use Wake Word</label>
          <select
            id="use_wake_word"
            value={voiceState.use_wake_word ? "true" : "false"}
            onChange={(event) =>
              setVoiceState((prev) => ({
                ...prev,
                use_wake_word: event.target.value === "true"
              }))
            }
          >
            <option value="true">Enabled</option>
            <option value="false">Push-to-talk</option>
          </select>
        </div>
        <div>
          <label htmlFor="transcription_provider">Transcription Provider</label>
          <input
            id="transcription_provider"
            value={voiceState.transcription_provider ?? ""}
            onChange={(event) =>
              setVoiceState((prev) => ({
                ...prev,
                transcription_provider: event.target.value
              }))
            }
          />
        </div>
        <div>
          <label htmlFor="transcription_language">Transcription Language</label>
          <input
            id="transcription_language"
            value={voiceState.transcription_language ?? ""}
            onChange={(event) =>
              setVoiceState((prev) => ({
                ...prev,
                transcription_language: event.target.value
              }))
            }
          />
        </div>
        <div>
          <label htmlFor="tts_voice">TTS Voice</label>
          <input
            id="tts_voice"
            value={voiceState.tts_voice ?? ""}
            onChange={(event) =>
              setVoiceState((prev) => ({ ...prev, tts_voice: event.target.value }))
            }
          />
        </div>
        <div>
          <label htmlFor="enable_tts">Enable TTS</label>
          <select
            id="enable_tts"
            value={voiceState.enable_tts ? "true" : "false"}
            onChange={(event) =>
              setVoiceState((prev) => ({
                ...prev,
                enable_tts: event.target.value === "true"
              }))
            }
          >
            <option value="true">Enabled</option>
            <option value="false">Muted</option>
          </select>
        </div>
      </SectionCard>

      <SectionCard
        title="Memory Store"
        description="Manage persistence path and short-term history window."
        footer={
          <button onClick={handleMemorySave} disabled={patchMutation.isLoading}>
            {patchMutation.isLoading ? "Saving…" : "Save"}
          </button>
        }
        layout="two"
      >
        <div>
          <label htmlFor="memory_path">Database Path</label>
          <input
            id="memory_path"
            value={memoryState.db_path ?? ""}
            onChange={(event) =>
              setMemoryState((prev) => ({ ...prev, db_path: event.target.value }))
            }
          />
        </div>
        <div>
          <label htmlFor="history_window">History Window</label>
          <input
            id="history_window"
            type="number"
            value={memoryState.history_window ?? 0}
            onChange={(event) =>
              setMemoryState((prev) => ({
                ...prev,
                history_window: event.target.value
              }))
            }
          />
        </div>
      </SectionCard>

      <SectionCard
        title="Safety Envelope"
        description="Control default privilege tier and audit log target."
        footer={
          <button onClick={handleSafetySave} disabled={patchMutation.isLoading}>
            {patchMutation.isLoading ? "Saving…" : "Save"}
          </button>
        }
        layout="two"
      >
        <div>
          <label htmlFor="default_privilege">Default Privilege</label>
          <select
            id="default_privilege"
            value={safetyState.default_privilege ?? ""}
            onChange={(event) =>
              setSafetyState((prev) => ({
                ...prev,
                default_privilege: event.target.value
              }))
            }
          >
            <option value="informational">Informational</option>
            <option value="command">Command</option>
          </select>
        </div>
        <div>
          <label htmlFor="pause_on_start">Pause On Start</label>
          <select
            id="pause_on_start"
            value={safetyState.pause_on_start ? "true" : "false"}
            onChange={(event) =>
              setSafetyState((prev) => ({
                ...prev,
                pause_on_start: event.target.value === "true"
              }))
            }
          >
            <option value="false">Resume Immediately</option>
            <option value="true">Require Manual Resume</option>
          </select>
        </div>
        <div style={{ gridColumn: "1 / -1" }}>
          <label htmlFor="audit_log_path">Audit Log Path</label>
          <input
            id="audit_log_path"
            value={safetyState.audit_log_path ?? ""}
            onChange={(event) =>
              setSafetyState((prev) => ({ ...prev, audit_log_path: event.target.value }))
            }
          />
        </div>
      </SectionCard>

      <SectionCard
        title="Session Preferences"
        description="Inspect and update persisted user preferences."
        footer={
          <button className="secondary" onClick={() => refetchPreferences()} disabled={loadingPreferences}>
            {loadingPreferences ? "Refreshing…" : "Refresh"}
          </button>
        }
      >
        <div style={{ gridColumn: "1 / -1" }}>
          <label htmlFor="session_id">Session</label>
          <input
            id="session_id"
            value={sessionId}
            onChange={(event) => setSessionId(event.target.value)}
          />
        </div>
        <div style={{ gridColumn: "1 / -1" }}>
          {Object.keys(preferences).length === 0 ? (
            <p style={{ color: "#64748b" }}>(No preferences stored)</p>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Key</th>
                  <th>Value</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(preferences).map(([key, value]) => (
                  <tr key={key}>
                    <td>{key}</td>
                    <td>{value}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
        <div style={{ gridColumn: "1 / -1" }}>
          <form onSubmit={handlePreferenceSubmit} className="grid two" style={{ gap: "16px" }}>
            <div>
              <label htmlFor="pref_key">Preference Key</label>
              <input
                id="pref_key"
                value={preferenceDraft.key}
                onChange={(event) =>
                  setPreferenceDraft((prev) => ({ ...prev, key: event.target.value }))
                }
              />
            </div>
            <div>
              <label htmlFor="pref_value">Value</label>
              <input
                id="pref_value"
                value={preferenceDraft.value}
                onChange={(event) =>
                  setPreferenceDraft((prev) => ({ ...prev, value: event.target.value }))
                }
              />
            </div>
            <div className="button-row" style={{ gridColumn: "1 / -1", justifyContent: "flex-start" }}>
              <button type="submit" disabled={preferenceMutation.isLoading}>
                {preferenceMutation.isLoading ? "Writing…" : "Save Preference"}
              </button>
            </div>
          </form>
        </div>
      </SectionCard>

      <SectionCard
        title="Safety Audit Log"
        description="Review recent tool invocations and safety actions."
        footer={
          <button className="secondary" onClick={() => refetchSafetyLog()} disabled={loadingSafetyLog}>
            {loadingSafetyLog ? "Refreshing…" : "Refresh"}
          </button>
        }
      >
        <div style={{ gridColumn: "1 / -1" }}>
          {safetyLog.length === 0 ? (
            <p style={{ color: "#64748b" }}>(No audit events logged yet)</p>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Event</th>
                  <th>Detail</th>
                </tr>
              </thead>
              <tbody>
                {safetyLog.map((entry, index) => (
                  <tr key={`${entry.ts ?? index}-${entry.event}`}>
                    <td>{entry.ts ? new Date(entry.ts * 1000).toLocaleTimeString() : "—"}</td>
                    <td>{entry.event}</td>
                    <td>
                      <code>{JSON.stringify(entry.detail ?? entry, null, 0)}</code>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </SectionCard>
    </div>
  );
}
