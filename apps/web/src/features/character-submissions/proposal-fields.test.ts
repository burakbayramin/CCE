import { describe, expect, it } from 'vitest';
import { axes, confirmations, contract, lists, texts } from './proposal-fields';

describe('proposal form contract', () => {
  it('renders every validated field exactly once', () => {
    expect(texts.map(([key]) => key).sort()).toEqual(Object.keys(contract.texts).sort());
    expect(lists.map(([key]) => key).sort()).toEqual(Object.keys(contract.lists).sort());
    expect(axes.map(([key]) => key).sort()).toEqual(Object.keys(contract.axes).sort());
    expect(confirmations.map(([key]) => key).sort()).toEqual(contract.confirmations);
  });
});
