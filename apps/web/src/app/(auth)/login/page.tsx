import { AuthForm } from '../../../components/auth-form';
export const dynamic = 'force-dynamic';
export default async function Login({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const params = await searchParams;
  return <AuthForm mode="login" error={Boolean(params.error)} confirm={params.notice === 'confirm'} />;
}
