interface SectionHeadProps {
  children: React.ReactNode;
  action?: string;
  actionHref?: string;
}

export function SectionHead({ children, action, actionHref }: SectionHeadProps) {
  return (
    <div className="section-h">
      <div className="t">{children}</div>
      <div className="rule" />
      {action ? (
        actionHref ? (
          <a className="a" href={actionHref}>
            {action}
          </a>
        ) : (
          <span className="a">{action}</span>
        )
      ) : null}
    </div>
  );
}
