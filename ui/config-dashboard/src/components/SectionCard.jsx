export function SectionCard({ title, description, footer, children, layout = "" }) {
  const layoutClass = layout ? ` ${layout}` : "";
  return (
    <div className="card">
      <div>
        <h2>{title}</h2>
        {description ? <p style={{ margin: "8px 0 0", color: "#475569" }}>{description}</p> : null}
      </div>
      <div className={`grid${layoutClass}`}>{children}</div>
      {footer ? <div className="button-row">{footer}</div> : null}
    </div>
  );
}
