import type { LeaderboardData } from '../api/types';
import { Avatar } from './Bits';

export function LeaderTable({ data, markMe = false }: { data: LeaderboardData; markMe?: boolean }) {
  return (
    <table className="table">
      <thead>
        <tr><th>#</th><th>Colleague</th><th className="table__num">{data.column_label}</th></tr>
      </thead>
      <tbody>
        {data.entries.map((e) => (
          <tr key={e.user_id} className={markMe && e.is_me ? 'is-me' : ''}>
            <td className="table__rank">{e.rank}</td>
            <td><span className="table__person"><Avatar initials={e.initials} />{e.name}{markMe && e.is_me ? ' (you)' : ''}</span></td>
            <td className="table__num">{e.value}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
