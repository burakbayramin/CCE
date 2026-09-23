import { redirect } from 'next/navigation';
import { IdentityPanel } from '../../components/identity-panel';
import { requireIdentity } from '../../lib/identity';
export const dynamic = 'force-dynamic';
export default async function Contributor() {
  const identity = await requireIdentity();
  if (identity?.role === 'world_owner') redirect('/admin');
  return <IdentityPanel identity={identity} />;
}
