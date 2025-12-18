export default function EnvCheckPage() {
  return (
    <div style={{ padding: 24 }}>
      <h1>Env Check</h1>
      <pre>{JSON.stringify({
        VITE_SUPABASE_URL: import.meta.env.VITE_SUPABASE_URL,
        VITE_API_BASE_URL: import.meta.env.VITE_API_BASE_URL,
      }, null, 2)}</pre>
    </div>
  );
}

