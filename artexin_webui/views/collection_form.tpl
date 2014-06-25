% rebase('base.tpl', title='Collect webpages')
<h1>Collect webpages</h1>
<p class="form-notes">
Paste URLs one per line and submit. Please give it some time before the request 
is completed. It may take several minutes or more depending on the number of 
URls and number of images in the pages.
</p>
<form action="/collections/" method="POST" class="collect-form">
    <textarea id="urls" name="urls"></textarea>
    <p class="buttons">
    <button type="submit">Process</button>
    </p>
</form>
