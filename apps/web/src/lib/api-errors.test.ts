import { describe, expect, it } from 'vitest';
import { apiErrorMessage } from './api-errors';

describe('API errors', () => {
  it('keeps actionable HTTP failures distinct', () => {
    const error = 'Sunucu ayrıntısı';
    expect(apiErrorMessage({ data: null, error, status: 404 })).toContain('bulunamadı');
    expect(apiErrorMessage({ data: null, error, status: 409 })).toContain('sayfayı yenile');
    expect(apiErrorMessage({ data: null, error, status: 422 })).toContain('alanları kontrol et');
    expect(apiErrorMessage({ data: null, error, status: 429 })).toContain('İstek sınırı');
    expect(apiErrorMessage({ data: null, error, status: 503 })).toContain('geçici');
    expect(apiErrorMessage({ data: null, error })).toBe(error);
  });
});
