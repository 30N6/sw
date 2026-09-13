N = 1024;

ifft_index_map = [0, (N-1):-1:1];

print_vector(ifft_index_map);

function print_vector(v)
    
    fprintf('(');
    for ii = 1:length(v)
        fprintf('%d', v(ii));
        if ii == length(v)
            fprintf(')\n');
        else
            fprintf(', ');
        end
    end
end