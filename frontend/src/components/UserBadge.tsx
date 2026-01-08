import { useMe } from "@/context/MeContext";

export function UserBadge() {
  const { me, loading } = useMe();

  if (loading) return null;
  if (!me) return <span style={{ fontSize: 'var(--rd-font-size-xs)', opacity: 0.7 }}>Not signed in</span>;

  return (
    <span style={{ fontSize: 'var(--rd-font-size-xs)', opacity: 0.7 }}>
      Signed in as {me.email}
    </span>
  );
}

