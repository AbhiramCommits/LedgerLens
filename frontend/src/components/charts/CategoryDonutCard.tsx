import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';
import { CATEGORY_COLORS, categoryLabel } from '../../lib/categories';
import { formatCurrency } from '../../lib/format';
import { EmptyState } from '../EmptyState';

export interface CategorySlice {
  category: string;
  total: number;
}

interface CategoryDonutCardProps {
  data: CategorySlice[];
}

export function CategoryDonutCard({ data }: CategoryDonutCardProps) {
  if (data.length === 0) {
    return (
      <EmptyState
        title="No spending this month"
        description="Import and categorize transactions to see a breakdown."
      />
    );
  }

  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
      <div className="h-52 w-full sm:w-1/2">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="total"
              nameKey="category"
              innerRadius="55%"
              outerRadius="82%"
              paddingAngle={2}
              stroke="none"
            >
              {data.map((entry) => (
                <Cell
                  key={entry.category}
                  fill={
                    CATEGORY_COLORS[entry.category as keyof typeof CATEGORY_COLORS] ?? '#94a3b8'
                  }
                />
              ))}
            </Pie>
            <Tooltip
              formatter={(value, name) => [
                formatCurrency(Number(value)),
                categoryLabel(String(name)),
              ]}
              contentStyle={{
                background: '#0f172a',
                border: '1px solid #334155',
                borderRadius: 8,
                fontSize: 12,
              }}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <ul className="grid w-full grid-cols-1 gap-1.5 sm:w-1/2">
        {data.map((entry) => (
          <li key={entry.category} className="flex items-center justify-between gap-2 text-sm">
            <span className="flex items-center gap-2 text-slate-300">
              <span
                className="h-2.5 w-2.5 shrink-0 rounded-full"
                style={{
                  backgroundColor:
                    CATEGORY_COLORS[entry.category as keyof typeof CATEGORY_COLORS] ?? '#94a3b8',
                }}
                aria-hidden="true"
              />
              {categoryLabel(entry.category)}
            </span>
            <span className="text-slate-200">{formatCurrency(entry.total)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
