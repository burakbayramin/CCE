import type { ApiResult } from './contributions';

export function apiErrorMessage(result: ApiResult<unknown>): string {
  if (!result.error) return '';
  switch (result.status) {
    case 404:
      return 'Kayıt bulunamadı veya erişim iznin yok.';
    case 409:
      return `Kayıt değişti; sayfayı yenile. ${result.error}`;
    case 422:
      return `Gönderilen alanları kontrol et. ${result.error}`;
    case 429:
      return `İstek sınırı doldu; daha sonra yeniden dene. ${result.error}`;
    case 503:
      return `Servis geçici olarak kullanılamıyor. ${result.error}`;
    default:
      return result.error;
  }
}
