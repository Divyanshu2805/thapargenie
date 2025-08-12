import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';

/** iPhone and iPad Safari have no install prompt; this is how it's done there. */
export default function IosInstallDialog({ open, onOpenChange }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Install ThaparGenie</DialogTitle>
          <DialogDescription>Add it to your Home Screen to open it like an app.</DialogDescription>
        </DialogHeader>
        <ol className="list-decimal space-y-2 pl-5 text-sm leading-relaxed">
          <li>
            Tap <span className="font-semibold">Share</span> in Safari’s toolbar (the square with an arrow).
          </li>
          <li>
            Choose <span className="font-semibold">Add to Home Screen</span>, then <span className="font-semibold">Add</span>.
          </li>
        </ol>
        <DialogFooter>
          <Button onClick={() => onOpenChange(false)}>Got it</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
