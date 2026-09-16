import type { ButtonHTMLAttributes, ReactNode } from 'react';

const VARIANTS = {
  primary: 'bg-indigo-600 text-white hover:bg-indigo-500 disabled:hover:bg-indigo-600',
  secondary:
    'border border-slate-700 bg-slate-800 text-slate-100 hover:bg-slate-700 disabled:hover:bg-slate-800',
  danger: 'bg-red-600 text-white hover:bg-red-500 disabled:hover:bg-red-600',
  ghost: 'bg-transparent text-slate-300 hover:bg-slate-800 disabled:hover:bg-transparent',
} as const;

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: keyof typeof VARIANTS;
  children: ReactNode;
}

export function Button({ variant = 'primary', className = '', children, ...rest }: ButtonProps) {
  return (
    <button
      type="button"
      className={`inline-flex items-center justify-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${VARIANTS[variant]} ${className}`}
      {...rest}
    >
      {children}
    </button>
  );
}
