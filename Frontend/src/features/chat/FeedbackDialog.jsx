import { useState } from 'react';

import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';

const FEEDBACK_REASONS = [
  { value: 'incorrect', label: 'Incorrect' },
  { value: 'outdated', label: 'Outdated' },
  { value: 'incomplete', label: 'Incomplete' },
  { value: 'irrelevant', label: 'Not what I asked' },
  { value: 'unclear', label: 'Hard to understand' },
  { value: 'other', label: 'Something else' },
];

export default function FeedbackDialog({ open, onOpenChange, onSubmit, initial }) {
  const [reason, setReason] = useState(initial?.reason || null);
  const [comment, setComment] = useState(initial?.comment || '');

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>What went wrong?</DialogTitle>
          <DialogDescription>
            Your feedback goes to the ThaparGenie team without your name or email, and helps fix the answer for everyone.
          </DialogDescription>
        </DialogHeader>
        <form
          className="grid gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            onSubmit({ reason, comment: comment.trim() });
          }}
        >
          <div role="radiogroup" aria-label="Reason" className="flex flex-wrap gap-2">
            {FEEDBACK_REASONS.map((item) => (
              <button
                key={item.value}
                type="button"
                role="radio"
                aria-checked={reason === item.value}
                onClick={() => setReason(reason === item.value ? null : item.value)}
                className={cn(
                  'rounded-full border px-3 py-1.5 text-sm transition-colors outline-none hover:border-primary/40 hover:bg-hover hover:text-accent-foreground focus-visible:ring-[3px] focus-visible:ring-ring/30',
                  reason === item.value && 'border-primary bg-accent text-accent-foreground hover:bg-accent',
                )}
              >
                {item.label}
              </button>
            ))}
          </div>
          <div className="grid content-start gap-2">
            <Label htmlFor="feedback-comment">Details (optional)</Label>
            <Textarea
              id="feedback-comment"
              value={comment}
              maxLength={1000}
              onChange={(event) => setComment(event.target.value)}
              placeholder="What should the answer have said? Don’t include personal information."
              className="min-h-24"
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit">Send feedback</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
