from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("evidence", "0011_fixture_audit"), ("identity", "0003_retiredrefresh")]
    operations = [
        migrations.RunSQL("""
ALTER TABLE public.identity_retiredrefresh ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.identity_retiredrefresh FORCE ROW LEVEL SECURITY;
GRANT SELECT,INSERT ON public.identity_retiredrefresh TO retiro_evidence_writer;
CREATE POLICY internal_writer ON public.identity_retiredrefresh
  TO retiro_evidence_writer USING (true) WITH CHECK (true);

CREATE OR REPLACE FUNCTION public.e1_refresh(old_refresh text, new_access text, new_refresh text)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE s public.identity_session; a public.identity_account; stamp timestamptz:=clock_timestamp();
BEGIN
  SELECT * INTO s FROM public.identity_session WHERE refresh_hash=old_refresh FOR UPDATE;
  IF NOT FOUND THEN
    SELECT session.* INTO s FROM public.identity_session session
      JOIN public.identity_retiredrefresh retired ON retired.session_id=session.id
      WHERE retired.token_hash=old_refresh FOR UPDATE OF session;
    IF FOUND AND s.revoked_at IS NULL THEN
      UPDATE public.identity_session SET revoked_at=stamp WHERE id=s.id;
      PERFORM public.e1_append('SESSION_REFRESH_REPLAY',s.account_id,
        (SELECT school_id FROM public.identity_account WHERE id=s.account_id),s.id,
        jsonb_build_object('result','REVOKED'));
    END IF;
    RETURN false;
  END IF;
  SELECT * INTO a FROM public.identity_account WHERE id=s.account_id FOR SHARE;
  IF s.channel<>'mobile' OR s.revoked_at IS NOT NULL OR NOT a.active OR
    a.version<>s.account_version OR s.expires_at<=stamp OR s.enabled_at IS NULL OR
    s.last_seen_at<=stamp-(CASE WHEN a.role='GUARDIA' THEN interval '5 minutes'
      ELSE interval '15 minutes' END)
    OR (a.school_id IS NOT NULL AND NOT EXISTS
      (SELECT 1 FROM public.school_roster_school WHERE id=a.school_id AND active)) THEN
    RETURN false;
  END IF;
  IF new_access !~ '^[0-9a-f]{64}$' OR new_refresh !~ '^[0-9a-f]{64}$'
    OR new_refresh=old_refresh THEN RETURN false; END IF;
  INSERT INTO public.identity_retiredrefresh(token_hash,session_id,retired_at)
    VALUES(old_refresh,s.id,stamp);
  UPDATE public.identity_session SET access_hash=new_access,refresh_hash=new_refresh,
    access_expires_at=stamp+interval '5 minutes',last_seen_at=stamp WHERE id=s.id;
  RETURN true;
END $$;

CREATE OR REPLACE FUNCTION public.e1_logout(token_hash text) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE s public.identity_session;
BEGIN
  SELECT * INTO s FROM public.identity_session
    WHERE access_hash=token_hash OR refresh_hash=token_hash FOR UPDATE;
  IF NOT FOUND THEN
    -- A new statement sees history committed by a refresh that won the row-lock race.
    SELECT session.* INTO s FROM public.identity_session session
      JOIN public.identity_retiredrefresh retired ON retired.session_id=session.id
      WHERE retired.token_hash=e1_logout.token_hash FOR UPDATE OF session;
  END IF;
  IF FOUND AND s.revoked_at IS NULL THEN
    UPDATE public.identity_session SET revoked_at=clock_timestamp() WHERE id=s.id;
    PERFORM public.e1_append('SESSION_CLOSED',s.account_id,
      (SELECT school_id FROM public.identity_account WHERE id=s.account_id),s.id,
      jsonb_build_object('result','REVOKED'));
  END IF;
END $$;
""")
    ]
