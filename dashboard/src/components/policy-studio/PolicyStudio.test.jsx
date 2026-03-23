/**
 * Policy Studio: stepper navigation and step content rendering.
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import PolicyStudio from './PolicyStudio';

describe('PolicyStudio', () => {
  it('renders stepper with step labels', () => {
    const onClose = vi.fn();
    render(<PolicyStudio onClose={onClose} onSaved={vi.fn()} />);
    const stepper = screen.getByRole('button', { name: 'Basics' }).closest('div');
    expect(stepper).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Source' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Scope' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Rules' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Review' })).toBeInTheDocument();
  });

  it('renders Basics step content by default', () => {
    render(<PolicyStudio onClose={vi.fn()} onSaved={vi.fn()} />);
    expect(screen.getByText('Policy name')).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/block high-risk/i)).toBeInTheDocument();
  });

  it('Continue button is present on Basics step', () => {
    render(<PolicyStudio onClose={vi.fn()} onSaved={vi.fn()} />);
    expect(screen.getByRole('button', { name: /continue/i })).toBeInTheDocument();
  });
});
