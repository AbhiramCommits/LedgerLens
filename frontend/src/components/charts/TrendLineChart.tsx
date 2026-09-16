import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { formatCurrency, formatShortMonth } from '../../lib/format';

export interface TrendPoint {
  month: string;
  spend: number;
  income: number;
}

interface TrendLineChartProps {
  data: TrendPoint[];
}

export function TrendLineChart({ data }: TrendLineChartProps) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
        <XAxis dataKey="month" tickFormatter={formatShortMonth} stroke="#64748b" fontSize={12} />
        <YAxis
          stroke="#64748b"
          fontSize={12}
          width={64}
          tickFormatter={(value) => `$${Math.round(value)}`}
        />
        <Tooltip
          formatter={(value, name) => [
            formatCurrency(Number(value)),
            name === 'spend' ? 'Spend' : 'Income',
          ]}
          labelFormatter={(label) => formatShortMonth(String(label))}
          contentStyle={{
            background: '#0f172a',
            border: '1px solid #334155',
            borderRadius: 8,
            fontSize: 12,
          }}
        />
        <Legend />
        <Line
          type="monotone"
          dataKey="spend"
          name="Spend"
          stroke="#ef4444"
          strokeWidth={2}
          dot={false}
        />
        <Line
          type="monotone"
          dataKey="income"
          name="Income"
          stroke="#22c55e"
          strokeWidth={2}
          dot={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
