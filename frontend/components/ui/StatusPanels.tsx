export function LoadingPanel({ message = "Loading..." }: { message?: string }) {
  return (
    <section className="panel" aria-live="polite">
      <p>{message}</p>
    </section>
  );
}

export function ErrorPanel({
  title = "Something went wrong",
  message,
  onRetry,
}: {
  title?: string;
  message: string;
  onRetry?: () => void;
}) {
  return (
    <section className="panel panel-warning" role="alert">
      <h2>{title}</h2>
      <p>{message}</p>
      {onRetry ? (
        <button type="button" className="secondary-button" onClick={onRetry}>
          Retry
        </button>
      ) : null}
    </section>
  );
}

export function EmptyPanel({ title, message }: { title: string; message: string }) {
  return (
    <section className="panel">
      <h2>{title}</h2>
      <p>{message}</p>
    </section>
  );
}
