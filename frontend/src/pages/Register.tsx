import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { ArrowRight, ShoppingBasket, Sprout } from 'lucide-react';
import { api } from '../lib/api';
import type { User } from '../types';

const schema = z
  .object({
    name: z.string().min(2, 'Name must be at least 2 characters').max(120, 'Name is too long'),
    email: z.string().min(1, 'Email is required').email('Enter a valid email address'),
    password: z.string().min(8, 'Password must be at least 8 characters'),
    confirm: z.string().min(1, 'Confirm your password'),
    phone: z.string().optional(),
    role: z.enum(['buyer', 'farmer']),
  })
  .refine((d) => d.password === d.confirm, {
    message: 'Passwords do not match',
    path: ['confirm'],
  });

type FormValues = z.infer<typeof schema>;

const roles = [
  { value: 'buyer' as const, label: 'Buyer', hint: 'Order produce', Icon: ShoppingBasket },
  { value: 'farmer' as const, label: 'Farmer', hint: 'Sell produce', Icon: Sprout },
];

export default function Register({ onLogin }: { onLogin: (u: User) => void }) {
  const nav = useNavigate();
  const [serverError, setServerError] = useState('');
  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { name: '', email: '', password: '', confirm: '', phone: '', role: 'buyer' },
  });

  const role = watch('role');

  const onSubmit = async (data: FormValues) => {
    setServerError('');
    try {
      const r = await api.register({
        name: data.name.trim(),
        email: data.email.trim(),
        password: data.password,
        role: data.role,
        phone: data.phone?.trim() || undefined,
      });
      localStorage.token = r.access_token;
      onLogin(r.user);
      nav('/dashboard');
    } catch (e) {
      setServerError(e instanceof Error ? e.message : 'Unable to create your account');
    }
  };

  return (
    <main className="auth">
      <span className="eyebrow">Get started</span>
      <h1>Build a shorter path from farm to table.</h1>
      <p>Create your account in a minute. You can start browsing or listing straight away.</p>

      <form onSubmit={handleSubmit(onSubmit)} noValidate>
        <label>
          Full name
          <input {...register('name')} type="text" autoComplete="name" />
          {errors.name && <span className="error">{errors.name.message}</span>}
        </label>

        <label>
          Email
          <input {...register('email')} type="email" autoComplete="email" />
          {errors.email && <span className="error">{errors.email.message}</span>}
        </label>

        <label>
          Password
          <input {...register('password')} type="password" autoComplete="new-password" />
          {errors.password && <span className="error">{errors.password.message}</span>}
        </label>

        <label>
          Confirm password
          <input {...register('confirm')} type="password" autoComplete="new-password" />
          {errors.confirm && <span className="error">{errors.confirm.message}</span>}
        </label>

        <label>
          Phone <span className="muted">(optional)</span>
          <input {...register('phone')} type="tel" autoComplete="tel" />
          {errors.phone && <span className="error">{errors.phone.message}</span>}
        </label>

        <div>
          <span className="eyebrow">I am a</span>
          <div className="demo-list">
            {roles.map(({ value, label, hint, Icon }) => (
              <button
                key={value}
                type="button"
                onClick={() => setValue('role', value, { shouldValidate: true })}
                aria-pressed={role === value}
                style={role === value ? { borderColor: '#23643e', background: '#f1f7ee' } : undefined}
              >
                <span>
                  <Icon size={18} />
                </span>
                <b>{label}</b>
                <small>{role === value ? 'Selected' : hint}</small>
              </button>
            ))}
          </div>
        </div>

        {serverError && <p className="error">{serverError}</p>}

        <button className="button" type="submit" disabled={isSubmitting}>
          {isSubmitting ? 'Creating account…' : 'Create account'} <ArrowRight size={18} />
        </button>
      </form>

      <p>
        Already have an account? <Link to="/login">Sign in</Link>
      </p>
    </main>
  );
}
