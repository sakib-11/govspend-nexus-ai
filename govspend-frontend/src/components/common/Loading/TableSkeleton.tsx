import React from 'react';
import { Skeleton, TableRow, TableCell, Box } from '@mui/material';

interface TableSkeletonProps {
  columns: number;
  rows?: number;
}

export const TableSkeleton: React.FC<TableSkeletonProps> = ({ columns, rows = 5 }) => {
  return (
    <>
      {Array.from({ length: rows }).map((_, rIdx) => (
        <TableRow key={`skeleton-row-${rIdx}`} sx={{ '&:last-child td, &:last-child th': { border: 0 } }}>
          {Array.from({ length: columns }).map((_, cIdx) => (
            <TableCell key={`skeleton-cell-${rIdx}-${cIdx}`} sx={{ borderBottom: '1px solid rgba(148, 163, 184, 0.06)' }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                <Skeleton
                  variant="text"
                  height={22}
                  width={cIdx === 0 ? '55%' : cIdx === columns - 1 ? '35%' : '75%'}
                  sx={{
                    borderRadius: 1,
                    background: 'linear-gradient(90deg, rgba(148, 163, 184, 0.06) 25%, rgba(148, 163, 184, 0.1) 50%, rgba(148, 163, 184, 0.06) 75%)',
                    backgroundSize: '200% 100%',
                    animation: 'shimmer 1.8s ease-in-out infinite',
                  }}
                />
                {cIdx === 0 && (
                  <Skeleton
                    variant="circular"
                    width={28}
                    height={28}
                    sx={{
                      borderRadius: '50%',
                      background: 'linear-gradient(90deg, rgba(148, 163, 184, 0.06) 25%, rgba(148, 163, 184, 0.1) 50%, rgba(148, 163, 184, 0.06) 75%)',
                      backgroundSize: '200% 100%',
                      animation: 'shimmer 1.8s ease-in-out infinite',
                      animationDelay: `${rIdx * 0.1}s`,
                    }}
                  />
                )}
              </Box>
            </TableCell>
          ))}
        </TableRow>
      ))}
    </>
  );
};

export default TableSkeleton;
