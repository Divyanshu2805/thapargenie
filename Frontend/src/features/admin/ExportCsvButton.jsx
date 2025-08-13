import { useMutation } from '@tanstack/react-query';
import { Download } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { downloadBlob, filenameFrom } from '@/lib/download';

/** Downloads a CSV from `request()` (an `apiBlobRequest`). */
export default function ExportCsvButton({ request, fallbackName, label = 'Export CSV' }) {
  const exportCsv = useMutation({
    mutationFn: request,
    onSuccess: ({ blob, contentDisposition }) => downloadBlob(blob, filenameFrom(contentDisposition, fallbackName)),
    onError: (error) => toast.error('Couldn’t export the CSV', { description: error.message }),
  });
  return (
    <Button variant="outline" size="sm" onClick={() => exportCsv.mutate()} disabled={exportCsv.isPending}>
      <Download /> {exportCsv.isPending ? 'Exporting…' : label}
    </Button>
  );
}
