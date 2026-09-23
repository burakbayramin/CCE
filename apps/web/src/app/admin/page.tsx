import { IdentityPanel } from '../../components/identity-panel';
import { requireIdentity } from '../../lib/identity';
export const dynamic = 'force-dynamic';
export default async function Admin() {
  return <IdentityPanel identity={await requireIdentity(true)} />;
}
