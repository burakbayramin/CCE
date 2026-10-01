import contract from './proposal-contract.json';

export const texts = [
  ['name', 'İsim', contract.texts.name], ['pronouns', 'Zamirler', contract.texts.pronouns],
  ['introduction', 'Kısa tanıtım', contract.texts.introduction],
  ['occupation', 'Meslek / rol', contract.texts.occupation],
  ['cultural_background', 'Kültürel arka plan', contract.texts.cultural_background],
  ['humor', 'Mizah', contract.texts.humor], ['speech_style', 'Konuşma tarzı', contract.texts.speech_style],
  ['backstory', 'Geçmiş hikâyesi', contract.texts.backstory],
] as const;
export const lists = [
  ['strengths', 'Güçlü yönler'], ['flaws', 'Kusurlar'], ['values', 'Değerler'],
  ['fears', 'Korkular'], ['motivations', 'Motivasyonlar'], ['likes', 'Sevdikleri'],
  ['dislikes', 'Sevmedikleri'], ['important_events', 'Önemli geçmiş olayları'],
  ['initial_goals', 'Başlangıç hedefi önerileri'],
  ['known_people', 'Bilinen kişi / kurum önerileri'], ['secret_proposals', 'Sır önerileri'],
] as const;
export const axes = [
  ['openness', 'Yeniliğe açıklık'], ['sociability', 'Sosyallik'],
  ['conscientiousness', 'Planlılık'], ['assertiveness', 'Kendini ifade etme'],
  ['warmth', 'Sıcaklık'],
] as const;
export const confirmations = [
  ['adult_appearance_confirmed', 'Karakter açıkça yetişkin görünür.'],
  ['original_character_confirmed', 'Gerçek bir kişinin izinsiz veya telifli bir karakterin birebir kopyası değildir; özel kişisel veri içermiyor.'],
] as const;

export { contract };
