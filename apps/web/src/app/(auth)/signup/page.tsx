import { AuthForm } from '../../../components/auth-form';
export const dynamic = 'force-dynamic';
export default async function Signup({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const params = await searchParams;
  return <AuthForm mode="signup" error={Boolean(params.error)} />;
}
