import { useQuery } from '@tanstack/react-query';
import { BookPlus, FlaskConical, SearchX } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';

import { PageHeader } from '@/components/layout/PageHeader';
import ExportCsvButton from '@/features/admin/ExportCsvButton';
import { SplitSection } from '@/components/split-section';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import AddKnowledgeDialog from '@/features/admin/AddKnowledgeDialog';
import { EmptyState, ErrorState, TableSkeleton } from '@/features/admin/components';
import { faqDraft } from '@/features/admin/FeedbackPage';
import { adminKeys, exportGapsCsv, listGaps } from '@/lib/api/admin';
import { formatNumber, formatRelative } from '@/lib/format';

export default function GapsPage() {
  const [range, setRange] = useState('30d');
  const [faqFor, setFaqFor] = useState(null);
  const gaps = useQuery({ queryKey: adminKeys.gaps(range), queryFn: () => listGaps(range) });
  const rows = gaps.data?.results || [];

  return (
    <div className="page-wide space-y-6">
      <PageHeader
        title="Knowledge gaps"
        description="Questions ThaparGenie couldn’t answer, ranked by how often they were asked."
        actions={
          <>
            <ExportCsvButton request={() => exportGapsCsv(range)} fallbackName="thapargenie-gaps.csv" />
            <Tabs value={range} onValueChange={setRange}>
              <TabsList aria-label="Time range">
                <TabsTrigger value="7d">7 days</TabsTrigger>
                <TabsTrigger value="30d">30 days</TabsTrigger>
              </TabsList>
            </Tabs>
          </>
        }
      />

      <SplitSection
        icon={SearchX}
        title="Unanswered questions"
        description="Grouped and ranked by how often they were asked. Add an FAQ or test a fix in the playground."
        flush
      >
        {gaps.isPending ? (
          <TableSkeleton />
        ) : gaps.isError ? (
          <ErrorState error={gaps.error} onRetry={() => gaps.refetch()} />
        ) : rows.length === 0 ? (
          <EmptyState icon={SearchX} title="No gaps in this period">
            Every question found an answer. Unanswered questions will be listed here.
          </EmptyState>
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead>Question (as searched)</TableHead>
                <TableHead className="text-right">Asked</TableHead>
                <TableHead className="hidden text-right sm:table-cell">Students</TableHead>
                <TableHead className="hidden text-right md:table-cell">Last asked</TableHead>
                <TableHead>
                  <span className="sr-only">Actions</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((gap) => (
                <TableRow key={gap.query}>
                  <TableCell className="max-w-md">
                    <p className="line-clamp-2">{gap.query || '(empty)'}</p>
                  </TableCell>
                  <TableCell className="text-right font-medium tabular-nums">{formatNumber(gap.count)}×</TableCell>
                  <TableCell className="hidden text-right tabular-nums sm:table-cell">{formatNumber(gap.askers)}</TableCell>
                  <TableCell className="hidden text-right text-muted-foreground md:table-cell">{formatRelative(gap.last_seen)}</TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-1">
                      <Button asChild variant="ghost" size="icon-sm" aria-label="Test in the playground">
                        <Link to="/admin/playground" state={{ query: gap.query }}>
                          <FlaskConical />
                        </Link>
                      </Button>
                      <Button variant="outline" size="sm" onClick={() => setFaqFor(gap)}>
                        <BookPlus /> <span className="hidden sm:inline">Create FAQ</span>
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </SplitSection>

      {faqFor ? <AddKnowledgeDialog open initial={faqDraft(faqFor.query)} onOpenChange={(open) => !open && setFaqFor(null)} /> : null}
    </div>
  );
}
